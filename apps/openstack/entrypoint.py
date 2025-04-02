#!/usr/bin/env python3
import os
import sys
import subprocess
import configparser
import logging
import shutil
import time
import json
import uuid
import stat
from pathlib import Path
import tempfile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('openstack-entrypoint')

# Configuration directories and files
CONFIG_DIRS = {
    'keystone': '/etc/keystone',
    'glance': '/etc/glance',
    'cinder': '/etc/cinder',
    'neutron': '/etc/neutron',
    'ironic': '/etc/ironic',
    'nova': '/etc/nova',
    'horizon': '/etc/openstack-dashboard'
}

CONFIG_FILES = {
    'keystone': '/app/config/keystone.conf',
    'glance': '/app/config/glance-api.conf',
    'cinder': '/app/config/cinder.conf',
    'neutron': '/app/config/neutron.conf',
    'ironic': '/app/config/ironic.conf',
    'nova': '/app/config/nova.conf'
}

# Make sure config directories exist
for service, directory in CONFIG_DIRS.items():
    os.makedirs(directory, exist_ok=True)

def run_command(cmd, shell=False):
    """Run a command and log output"""
    logger.info(f"Running command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        process = subprocess.run(
            cmd,
            shell=shell,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"Command output: {process.stdout}")
        return process.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with error: {e.stderr}")
        raise

def merge_config(source_config_path, service_name):
    """
    Merge default config with environment variables for the service
    """
    logger.info(f"Merging configuration for {service_name}")

    # Load the source config
    config = configparser.ConfigParser()
    config.read(source_config_path)

    # Get all environment variables for this service
    service_prefix = service_name.upper() + '_'
    for key, value in os.environ.items():
        if key.startswith(service_prefix):
            # Extract section and option from env var
            # Format: SERVICE_SECTION_OPTION=value
            parts = key[len(service_prefix):].split('_', 1)
            if len(parts) == 2:
                section, option = parts
                section = section.lower()
                option = option.lower()

                # Create section if it doesn't exist
                if section not in config:
                    config[section] = {}

                logger.info(f"  Setting {service_name} [{section}] {option} = {value}")
                config[section][option] = value

    # Get the target config file path
    target_path = os.path.join(CONFIG_DIRS[service_name.lower()],
                              os.path.basename(source_config_path))

    # Write the updated config
    with open(target_path, 'w') as f:
        config.write(f)

    logger.info(f"Configuration for {service_name} written to {target_path}")
    return target_path

def configure_database_connection(config_path, service):
    """Set the database connection string in a config file"""
    config = configparser.ConfigParser()
    config.read(config_path)

    # Check for the default database type
    default_db_type = os.environ.get('OPENSTACK_DEFAULT_DB_TYPE', 'postgresql')

    # Check if service-specific DB host is provided
    db_host = os.environ.get(f'{service.upper()}_DB_HOST')

    # Use SQLite in either of these cases:
    # 1. No DB host is provided
    # 2. Default DB type is explicitly set to 'sqlite'
    # 3. DB host is 'localhost' (can't run PostgreSQL in distroless)
    if db_host is None or default_db_type.lower() == 'sqlite' or db_host == 'localhost':
        # Configure SQLite3 database
        db_file = f'/var/lib/openstack/{service.lower()}.sqlite'
        connection = f'sqlite:///{db_file}'
        logger.info(f"Using SQLite database for {service} at {db_file}")
    else:
        # Configure PostgreSQL database for external servers
        db_user = os.environ.get(f'{service.upper()}_DB_USER', service.lower())
        db_pass = os.environ.get(f'{service.upper()}_DB_PASSWORD', service.lower())
        db_name = os.environ.get(f'{service.upper()}_DB_NAME', service.lower())
        connection = f'postgresql://{db_user}:{db_pass}@{db_host}/{db_name}'
        logger.info(f"Using PostgreSQL database for {service} at {db_host}")

    # Set the database connection
    if 'database' not in config:
        config['database'] = {}

    config['database']['connection'] = connection

    # Write updated config
    with open(config_path, 'w') as f:
        config.write(f)

    logger.info(f"Database connection for {service} configured: {connection}")

def enable_keystone_application_credentials(config_path):
    """Enable application credentials in Keystone configuration"""
    logger.info("Enabling application credentials in Keystone")

    config = configparser.ConfigParser()
    config.read(config_path)

    # Make sure application credential options are enabled
    if 'application_credential' not in config:
        config['application_credential'] = {}

    config['application_credential']['driver'] = 'sql'
    config['application_credential']['enable'] = 'True'

    # Write updated config
    with open(config_path, 'w') as f:
        config.write(f)

    logger.info("Application credentials enabled in Keystone configuration")

def create_application_credentials():
    """Create application credentials for each OpenStack service"""
    logger.info("Creating application credentials for OpenStack services")

    # Create a temporary file for admin credentials
    admin_creds = tempfile.NamedTemporaryFile(mode='w', delete=False)
    admin_creds.write(f"""
export OS_AUTH_URL=http://localhost:5000/v3
export OS_USERNAME=admin
export OS_PASSWORD={os.environ.get('KEYSTONE_ADMIN_PASSWORD', 'admin')}
export OS_PROJECT_NAME=admin
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_DOMAIN_NAME=Default
export OS_IDENTITY_API_VERSION=3
""")
    admin_creds.close()

    app_creds_dir = '/var/lib/openstack/app_credentials'
    os.makedirs(app_creds_dir, exist_ok=True)

    services = ['glance', 'cinder', 'neutron', 'ironic', 'nova', 'horizon']
    service_app_creds = {}

    try:
        # Source admin credentials
        source_cmd = f". {admin_creds.name}"

        # Make sure service project exists
        run_command([
            'bash', '-c',
            f"{source_cmd} && openstack project show service || openstack project create --domain default --description 'Service Project' service"
        ], shell=False)

        # Create application credentials for each service
        for service in services:
            # Check if service user exists, if not create it
            create_user_cmd = f"{source_cmd} && openstack user show {service} || openstack user create --domain default --password {service} {service}"
            run_command(['bash', '-c', create_user_cmd], shell=False)

            # Add service role to service user
            add_role_cmd = f"{source_cmd} && openstack role add --project service --user {service} service"
            try:
                run_command(['bash', '-c', add_role_cmd], shell=False)
            except subprocess.CalledProcessError:
                # Role might already exist, this is fine
                pass

            # Generate a unique application credential name for this service
            app_cred_name = f"{service}-{uuid.uuid4().hex[:8]}"
            secret = os.environ.get(f'{service.upper()}_APP_CRED_SECRET', uuid.uuid4().hex)

            # Create the application credential for the service
            create_app_cred_cmd = f"{source_cmd} && openstack application credential create --user {service} --secret {secret} {app_cred_name} -f json"
            app_cred_output = run_command(['bash', '-c', create_app_cred_cmd], shell=False)

            # Parse the application credential info from JSON output
            app_cred_info = json.loads(app_cred_output)

            # Store application credential info
            service_app_creds[service] = {
                'id': app_cred_info['id'],
                'name': app_cred_name,
                'secret': secret
            }

            # Save application credential to file for future use
            with open(f"{app_creds_dir}/{service}_app_cred.json", 'w') as f:
                f.write(json.dumps(service_app_creds[service], indent=2))

            logger.info(f"Created application credential for {service} service: {app_cred_name}")

    finally:
        # Clean up temporary admin credential file
        os.unlink(admin_creds.name)

    return service_app_creds

def configure_service_with_application_credential(config_path, service):
    """Configure a service to use application credentials for authentication"""
    logger.info(f"Configuring {service} to use application credentials")

    config = configparser.ConfigParser()
    config.read(config_path)

    # Check if application credential file exists
    app_cred_file = f'/var/lib/openstack/app_credentials/{service}_app_cred.json'
    if not os.path.exists(app_cred_file):
        logger.warning(f"Application credential file not found for {service}, skipping")
        return

    # Load application credential info
    with open(app_cred_file, 'r') as f:
        app_cred = json.loads(f.read())

    # Configure keystone authentication with application credentials
    if 'keystone_authtoken' not in config:
        config['keystone_authtoken'] = {}

    config['keystone_authtoken']['auth_type'] = 'v3applicationcredential'
    config['keystone_authtoken']['auth_url'] = 'http://localhost:5000/v3'
    config['keystone_authtoken']['application_credential_id'] = app_cred['id']
    config['keystone_authtoken']['application_credential_secret'] = app_cred['secret']

    # Write updated config
    with open(config_path, 'w') as f:
        config.write(f)

    logger.info(f"{service} configured to use application credentials")

def configure_keystone():
    """Configure Keystone service"""
    logger.info("Configuring Keystone")
    config_path = merge_config(CONFIG_FILES['keystone'], 'keystone')
    configure_database_connection(config_path, 'keystone')

    # Enable application credentials in Keystone config
    enable_keystone_application_credentials(config_path)

    # Bootstrap Keystone
    admin_pass = os.environ.get('KEYSTONE_ADMIN_PASSWORD', 'admin')
    bootstrap_cmd = [
        'keystone-manage', 'bootstrap',
        '--bootstrap-password', admin_pass,
        '--bootstrap-admin-url', 'http://localhost:5000/v3/',
        '--bootstrap-internal-url', 'http://localhost:5000/v3/',
        '--bootstrap-public-url', 'http://localhost:5000/v3/',
        '--bootstrap-region-id', 'RegionOne'
    ]

    try:
        # Run DB sync first
        run_command(['keystone-manage', 'db_sync'])
        # Then bootstrap
        run_command(bootstrap_cmd)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to bootstrap Keystone: {e}")
        sys.exit(1)

    # Create application credentials for services
    create_application_credentials()

def configure_glance():
    """Configure Glance service"""
    logger.info("Configuring Glance")
    config_path = merge_config(CONFIG_FILES['glance'], 'glance')
    configure_database_connection(config_path, 'glance')

    # Configure glance to use application credentials
    configure_service_with_application_credential(config_path, 'glance')

    try:
        run_command(['glance-manage', 'db_sync'])
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to sync Glance database: {e}")
        sys.exit(1)

def configure_cinder():
    """Configure Cinder service"""
    logger.info("Configuring Cinder")
    config_path = merge_config(CONFIG_FILES['cinder'], 'cinder')
    configure_database_connection(config_path, 'cinder')

    # Configure Cinder to use application credentials
    configure_service_with_application_credential(config_path, 'cinder')

    try:
        run_command(['cinder-manage', 'db', 'sync'])
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to sync Cinder database: {e}")
        sys.exit(1)

def configure_neutron():
    """Configure Neutron service"""
    logger.info("Configuring Neutron")
    config_path = merge_config(CONFIG_FILES['neutron'], 'neutron')
    configure_database_connection(config_path, 'neutron')

    # Configure Neutron to use application credentials
    configure_service_with_application_credential(config_path, 'neutron')

    try:
        run_command(['neutron-db-manage', 'upgrade', 'head'])
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to sync Neutron database: {e}")
        sys.exit(1)

def configure_ironic():
    """Configure Ironic service"""
    logger.info("Configuring Ironic")
    config_path = merge_config(CONFIG_FILES['ironic'], 'ironic')
    configure_database_connection(config_path, 'ironic')

    # Configure Ironic to use application credentials
    configure_service_with_application_credential(config_path, 'ironic')

    try:
        run_command(['ironic-dbsync', '--config-file', config_path, 'create_schema'])
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to sync Ironic database: {e}")
        sys.exit(1)

def configure_nova():
    """Configure Nova service"""
    logger.info("Configuring Nova")
    config_path = merge_config(CONFIG_FILES['nova'], 'nova')
    configure_database_connection(config_path, 'nova')

    # Configure Nova to use application credentials
    configure_service_with_application_credential(config_path, 'nova')

    # Configure Nova to use local Ironic instance
    config = configparser.ConfigParser()
    config.read(config_path)

    # Ensure ironic section exists
    if 'ironic' not in config:
        config['ironic'] = {}

    # Set up Nova to use local Ironic with application credentials
    app_cred_file = f'/var/lib/openstack/app_credentials/ironic_app_cred.json'
    if os.path.exists(app_cred_file):
        with open(app_cred_file, 'r') as f:
            ironic_app_cred = json.loads(f.read())

        # Configure Nova to use Ironic with application credentials
        config['ironic']['auth_type'] = 'v3applicationcredential'
        config['ironic']['auth_url'] = 'http://localhost:5000/v3'
        config['ironic']['application_credential_id'] = ironic_app_cred['id']
        config['ironic']['application_credential_secret'] = ironic_app_cred['secret']
    else:
        # Fallback to password auth if app creds not available
        config['ironic']['auth_type'] = 'password'
        config['ironic']['auth_url'] = 'http://localhost:5000/v3'
        config['ironic']['project_name'] = 'service'
        config['ironic']['username'] = 'ironic'
        config['ironic']['password'] = os.environ.get('IRONIC_SERVICE_PASSWORD', 'ironic')
        config['ironic']['user_domain_name'] = 'Default'
        config['ironic']['project_domain_name'] = 'Default'

    # Enable Ironic driver in Nova
    if 'DEFAULT' not in config:
        config['DEFAULT'] = {}

    config['DEFAULT']['compute_driver'] = 'ironic.IronicDriver'

    # Configure networking for Ironic instances with app credentials
    if 'neutron' not in config:
        config['neutron'] = {}

    app_cred_file = f'/var/lib/openstack/app_credentials/neutron_app_cred.json'
    if os.path.exists(app_cred_file):
        with open(app_cred_file, 'r') as f:
            neutron_app_cred = json.loads(f.read())

        # Configure Nova to use Neutron with application credentials
        config['neutron']['auth_type'] = 'v3applicationcredential'
        config['neutron']['auth_url'] = 'http://localhost:5000/v3'
        config['neutron']['application_credential_id'] = neutron_app_cred['id']
        config['neutron']['application_credential_secret'] = neutron_app_cred['secret']
    else:
        # Fallback to password auth if app creds not available
        config['neutron']['auth_type'] = 'password'
        config['neutron']['auth_url'] = 'http://localhost:5000/v3'
        config['neutron']['project_name'] = 'service'
        config['neutron']['username'] = 'neutron'
        config['neutron']['password'] = os.environ.get('NEUTRON_SERVICE_PASSWORD', 'neutron')
        config['neutron']['user_domain_name'] = 'Default'
        config['neutron']['project_domain_name'] = 'Default'

    # Set Nova API endpoints
    if 'DEFAULT' in config:
        config['DEFAULT']['osapi_compute_listen'] = '0.0.0.0'
        config['DEFAULT']['osapi_compute_listen_port'] = '8774'
        config['DEFAULT']['metadata_listen'] = '0.0.0.0'
        config['DEFAULT']['metadata_listen_port'] = '8775'

    # Write updated config
    with open(config_path, 'w') as f:
        config.write(f)

    try:
        # Run Nova DB sync
        run_command(['nova-manage', 'api_db', 'sync'])
        run_command(['nova-manage', 'cell_v2', 'map_cell0'])
        run_command(['nova-manage', 'cell_v2', 'create_cell', '--name=cell1', '--verbose'])
        run_command(['nova-manage', 'db', 'sync'])
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to sync Nova database: {e}")
        sys.exit(1)

    logger.info("Nova configuration complete")

def configure_horizon():
    """Configure Horizon dashboard"""
    logger.info("Configuring Horizon")

    # Create local_settings.py with correct configuration
    settings_path = '/etc/openstack-dashboard/local_settings.py'

    # Check if horizon application credential exists
    app_cred_file = '/var/lib/openstack/app_credentials/horizon_app_cred.json'
    horizon_app_cred = None
    if os.path.exists(app_cred_file):
        with open(app_cred_file, 'r') as f:
            horizon_app_cred = json.loads(f.read())
            logger.info("Using application credentials for Horizon")

    settings_content = f"""
import os

DEBUG = False
ALLOWED_HOSTS = ['*']
SECRET_KEY = '{os.environ.get('HORIZON_SECRET_KEY', 'supersecret')}'

# OpenStack API endpoints
OPENSTACK_HOST = '{os.environ.get('OPENSTACK_HOST', 'localhost')}'
OPENSTACK_KEYSTONE_URL = 'http://%s:5000/v3' % OPENSTACK_HOST
OPENSTACK_KEYSTONE_DEFAULT_ROLE = 'member'
OPENSTACK_KEYSTONE_MULTIDOMAIN_SUPPORT = True

# Database
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/var/lib/openstack/horizon.sqlite3',
    }}
}}

# Session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
CACHES = {{
    'default': {{
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }}
}}

# Configure API versions
OPENSTACK_API_VERSIONS = {{
    'identity': 3,
    'image': 2,
    'volume': 3,
}}

# Enable application credential auth in Horizon
AUTHENTICATION_PLUGINS = ['openstack_auth.plugin.password.Password',
                          'openstack_auth.plugin.application_credential.ApplicationCredential']
"""

    # If we have a horizon application credential, add the option to pre-populate fields
    if horizon_app_cred:
        settings_content += f"""
# Application credential settings for Horizon
APPLICATION_CREDENTIAL_SETTINGS = {{
    'application_credential_id': '{horizon_app_cred['id']}',
    'application_credential_secret': '{horizon_app_cred['secret']}'
}}
"""

    with open(settings_path, 'w') as f:
        f.write(settings_content)

    logger.info(f"Horizon configuration written to {settings_path}")

    # Set up static files
    try:
        # Find the manage.py file in the venv
        manage_script = None
        for path in Path('/app/venv').rglob('manage.py'):
            if 'horizon' in str(path) or 'openstack_dashboard' in str(path):
                manage_script = str(path)
                break

        if manage_script:
            logger.info(f"Found Horizon manage.py at {manage_script}")
            run_command(['python', manage_script, 'collectstatic', '--noinput'])
            run_command(['python', manage_script, 'compress', '--force'])
        else:
            logger.warning("Could not find Horizon manage.py script")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to configure Horizon static files: {e}")
        sys.exit(1)

def configure_apache():
    """Configure Apache for hosting OpenStack services"""
    logger.info("Configuring Apache")

    # Create a wsgi configuration directory
    wsgi_dir = tempfile.mkdtemp()

    # Create a wsgi configuration for Horizon
    horizon_conf = os.path.join(wsgi_dir, 'horizon.conf')
    with open(horizon_conf, 'w') as f:
        f.write("""
WSGIScriptAlias / /app/venv/bin/openstack-dashboard-wsgi
WSGIDaemonProcess horizon processes=3 threads=10
WSGIProcessGroup horizon
WSGIApplicationGroup %{GLOBAL}

<Directory /app/venv/bin>
    Require all granted
</Directory>
""")

    # Create a wsgi configuration for Keystone
    keystone_conf = os.path.join(wsgi_dir, 'keystone.conf')
    with open(keystone_conf, 'w') as f:
        f.write("""
Listen 5000
<VirtualHost *:5000>
    WSGIDaemonProcess keystone-public processes=5 threads=1
    WSGIProcessGroup keystone-public
    WSGIScriptAlias / /app/venv/bin/keystone-wsgi-public
    WSGIApplicationGroup %{GLOBAL}
    <Directory /app/venv/bin>
        Require all granted
    </Directory>
</VirtualHost>
""")

    return wsgi_dir, horizon_conf, keystone_conf

def start_services():
    """Start all OpenStack services"""
    logger.info("Starting OpenStack services")

    # Configure Apache
    wsgi_dir, horizon_conf, keystone_conf = configure_apache()

    # Start Apache with mod_wsgi
    apache_cmd = [
        '/app/venv/bin/mod_wsgi-express', 'start-server',
        '--port', '80',
        '--application-type', 'module',
        '--log-to-terminal',
        '--working-directory', '/app',
        '--include-file', horizon_conf,
        '--include-file', keystone_conf,
        '--server-root', '/tmp/mod_wsgi-httpd'
    ]

    logger.info("Starting Apache HTTP Server via mod_wsgi-express")
    apache_process = subprocess.Popen(apache_cmd)

    # Start Glance API
    logger.info("Starting Glance API")
    glance_api_cmd = ['glance-api', '--config-file', '/etc/glance/glance-api.conf']
    glance_api_process = subprocess.Popen(glance_api_cmd)

    # Start Cinder API
    logger.info("Starting Cinder API")
    cinder_api_cmd = ['cinder-api', '--config-file', '/etc/cinder/cinder.conf']
    cinder_api_process = subprocess.Popen(cinder_api_cmd)

    # Start Neutron Server
    logger.info("Starting Neutron Server")
    neutron_cmd = ['neutron-server', '--config-file', '/etc/neutron/neutron.conf']
    neutron_process = subprocess.Popen(neutron_cmd)

    # Start Ironic API
    logger.info("Starting Ironic API")
    ironic_api_cmd = ['ironic-api', '--config-file', '/etc/ironic/ironic.conf']
    ironic_api_process = subprocess.Popen(ironic_api_cmd)

    # Start Nova API
    logger.info("Starting Nova API")
    nova_api_cmd = ['nova-api', '--config-file', '/etc/nova/nova.conf']
    nova_api_process = subprocess.Popen(nova_api_cmd)

    # Start Nova Conductor
    logger.info("Starting Nova Conductor")
    nova_conductor_cmd = ['nova-conductor', '--config-file', '/etc/nova/nova.conf']
    nova_conductor_process = subprocess.Popen(nova_conductor_cmd)

    # Start Nova Scheduler
    logger.info("Starting Nova Scheduler")
    nova_scheduler_cmd = ['nova-scheduler', '--config-file', '/etc/nova/nova.conf']
    nova_scheduler_process = subprocess.Popen(nova_scheduler_cmd)

    # Start Nova Compute (with Ironic driver)
    logger.info("Starting Nova Compute with Ironic driver")
    nova_compute_cmd = ['nova-compute', '--config-file', '/etc/nova/nova.conf']
    nova_compute_process = subprocess.Popen(nova_compute_cmd)

    # Wait for all services
    logger.info("All OpenStack services started. Container is now running.")

    try:
        # Keep the container running
        while True:
            time.sleep(60)
            # Check if processes are still running
            if apache_process.poll() is not None:
                logger.error("Apache server exited unexpectedly")
                sys.exit(1)
            if glance_api_process.poll() is not None:
                logger.error("Glance API exited unexpectedly")
                sys.exit(1)
            if cinder_api_process.poll() is not None:
                logger.error("Cinder API exited unexpectedly")
                sys.exit(1)
            if neutron_process.poll() is not None:
                logger.error("Neutron Server exited unexpectedly")
                sys.exit(1)
            if ironic_api_process.poll() is not None:
                logger.error("Ironic API exited unexpectedly")
                sys.exit(1)
            if nova_api_process.poll() is not None:
                logger.error("Nova API exited unexpectedly")
                sys.exit(1)
            if nova_conductor_process.poll() is not None:
                logger.error("Nova Conductor exited unexpectedly")
                sys.exit(1)
            if nova_scheduler_process.poll() is not None:
                logger.error("Nova Scheduler exited unexpectedly")
                sys.exit(1)
            if nova_compute_process.poll() is not None:
                logger.error("Nova Compute exited unexpectedly")
                sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, stopping services...")
        apache_process.terminate()
        glance_api_process.terminate()
        cinder_api_process.terminate()
        neutron_process.terminate()
        ironic_api_process.terminate()
        nova_api_process.terminate()
        nova_conductor_process.terminate()
        nova_scheduler_process.terminate()
        nova_compute_process.terminate()

        # Clean up the temporary directory
        if os.path.exists(wsgi_dir):
            shutil.rmtree(wsgi_dir)

def prepare_service_directories():
    """
    Create all necessary directories and files required by OpenStack services
    """
    logger.info("Preparing service directories and files")

    # Create persistent storage directory
    os.makedirs('/var/lib/openstack', exist_ok=True)

    # Create data directories for each service
    services_data_dirs = {
        'keystone': [
            '/etc/keystone/fernet-keys',
            '/etc/keystone/credential-keys',
            '/var/log/keystone'
        ],
        'glance': [
            '/var/lib/glance/images',
            '/var/log/glance'
        ],
        'cinder': [
            '/var/lib/cinder/volumes',
            '/var/log/cinder'
        ],
        'neutron': [
            '/var/lib/neutron',
            '/var/log/neutron'
        ],
        'ironic': [
            '/var/lib/ironic',
            '/var/log/ironic'
        ],
        'nova': [
            '/var/lib/nova',
            '/var/lib/nova/instances',
            '/var/log/nova'
        ],
        'horizon': [
            '/var/log/horizon'
        ]
    }

    # Create all required directories
    for service, dirs in services_data_dirs.items():
        for directory in dirs:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")

    # Initialize Keystone fernet keys
    init_keystone_fernet_keys()

    # Create image storage directories for Glance
    glance_image_dir = '/var/lib/glance/images'
    os.makedirs(glance_image_dir, exist_ok=True)
    os.chmod(glance_image_dir, 0o750)  # Secure permissions for image storage

    # Create cinder volume directory
    cinder_volumes_dir = '/var/lib/cinder/volumes'
    os.makedirs(cinder_volumes_dir, exist_ok=True)

    # Create Nova instances directory
    nova_instances_dir = '/var/lib/nova/instances'
    os.makedirs(nova_instances_dir, exist_ok=True)

    # Create directories for application credentials
    app_creds_dir = '/var/lib/openstack/app_credentials'
    os.makedirs(app_creds_dir, exist_ok=True)

    logger.info("All service directories created successfully")

def init_keystone_fernet_keys():
    """
    Initialize Keystone fernet keys for token encryption
    """
    logger.info("Initializing Keystone fernet keys")

    # Fernet keys for tokens
    fernet_keys_dir = '/etc/keystone/fernet-keys'
    os.makedirs(fernet_keys_dir, exist_ok=True)

    # Create initial fernet key (key 0)
    if not os.path.exists(os.path.join(fernet_keys_dir, '0')):
        try:
            run_command(['keystone-manage', 'fernet_setup', '--keystone-user', 'root', '--keystone-group', 'root'])
            logger.info("Keystone fernet keys created successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create Keystone fernet keys: {e}")
            # Create a minimal key manually if command fails
            with open(os.path.join(fernet_keys_dir, '0'), 'w') as f:
                f.write('c_7Q3FIUcWR7vJUMgCJ42CWpV8s_Q27wnXP91c3-fc=')  # Example fernet key
            logger.info("Created a fallback fernet key manually")

    # Credential keys
    credential_keys_dir = '/etc/keystone/credential-keys'
    os.makedirs(credential_keys_dir, exist_ok=True)

    # Create initial credential key
    if not os.path.exists(os.path.join(credential_keys_dir, '0')):
        try:
            run_command(['keystone-manage', 'credential_setup', '--keystone-user', 'root', '--keystone-group', 'root'])
            logger.info("Keystone credential keys created successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create Keystone credential keys: {e}")
            # Create a minimal key manually if command fails
            with open(os.path.join(credential_keys_dir, '0'), 'w') as f:
                f.write('c_7Q3FIUcWR7vJUMgCJ42CWpV8s_Q27wnXP91c3-fc=')  # Example key
            logger.info("Created a fallback credential key manually")

    # Set proper permissions
    for directory in [fernet_keys_dir, credential_keys_dir]:
        for root, dirs, files in os.walk(directory):
            for f in files:
                os.chmod(os.path.join(root, f), 0o600)  # Secure permissions for keys

    logger.info("Keystone encryption keys initialized")

def main():
    """Main entrypoint function"""
    logger.info("Starting OpenStack services container")

    # Prepare service directories
    prepare_service_directories()

    # Configure all services
    configure_keystone()
    configure_glance()
    configure_cinder()
    configure_neutron()
    configure_ironic()
    configure_nova()
    configure_horizon()

    # Start all services
    start_services()

if __name__ == "__main__":
    main()
