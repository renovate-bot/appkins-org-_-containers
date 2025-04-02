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
import base64
import secrets
import asyncio
import uvicorn
import multiprocessing
from starlette.applications import Starlette
from starlette.routing import Mount
from cryptography.fernet import Fernet
from keystoneauth1 import session
from keystoneauth1.identity import v3
from keystoneclient.v3 import client as keystone_client

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
    """Create application credentials for each OpenStack service using Python API instead of shell commands"""
    logger.info("Creating application credentials for OpenStack services")

    admin_password = os.environ.get('KEYSTONE_ADMIN_PASSWORD', 'admin')
    app_creds_dir = '/var/lib/openstack/app_credentials'
    os.makedirs(app_creds_dir, exist_ok=True)

    services = ['glance', 'cinder', 'neutron', 'ironic', 'nova', 'horizon']
    service_app_creds = {}

    try:
        # Create admin auth and session for Keystone
        auth = v3.Password(
            auth_url='http://localhost:5000/v3',
            username='admin',
            password=admin_password,
            project_name='admin',
            user_domain_name='Default',
            project_domain_name='Default'
        )
        sess = session.Session(auth=auth)
        keystone = keystone_client.Client(session=sess)

        # Get or create service project
        try:
            service_project = keystone.projects.find(name='service')
            logger.info("Found existing service project")
        except Exception:
            logger.info("Creating service project")
            service_project = keystone.projects.create(
                name='service',
                domain='default',
                description='Service Project'
            )

        # Get or create service role
        try:
            service_role = keystone.roles.find(name='service')
            logger.info("Found existing service role")
        except Exception:
            logger.info("Creating service role")
            service_role = keystone.roles.create(name='service')

        # Create application credentials for each service
        for service_name in services:
            # Get or create service user
            try:
                service_user = keystone.users.find(name=service_name)
                logger.info(f"Found existing {service_name} user")
            except Exception:
                logger.info(f"Creating {service_name} user")
                service_user = keystone.users.create(
                    name=service_name,
                    password=service_name,
                    default_project=service_project,
                    domain='default'
                )

            # Assign service role to service user in service project
            try:
                # Check if role assignment already exists
                assignments = list(keystone.role_assignments.list(
                    user=service_user,
                    project=service_project,
                    role=service_role
                ))

                if not assignments:
                    logger.info(f"Assigning service role to {service_name}")
                    keystone.roles.grant(
                        role=service_role,
                        user=service_user,
                        project=service_project
                    )
            except Exception as e:
                logger.warning(f"Error assigning role: {e}")

            # Generate a unique application credential name and secret
            app_cred_name = f"{service_name}-{uuid.uuid4().hex[:8]}"
            secret = os.environ.get(f'{service_name.upper()}_APP_CRED_SECRET', uuid.uuid4().hex)

            # Create application credential
            try:
                # Use admin to impersonate service user for app cred creation
                service_auth = v3.Password(
                    auth_url='http://localhost:5000/v3',
                    username=service_name,
                    password=service_name,
                    project_name='service',
                    user_domain_name='Default',
                    project_domain_name='Default'
                )
                service_sess = session.Session(auth=service_auth)
                service_keystone = keystone_client.Client(session=service_sess)

                # Create the application credential
                app_cred = service_keystone.application_credentials.create(
                    name=app_cred_name,
                    secret=secret,
                    description=f"Application credential for {service_name} service"
                )

                # Store application credential info
                service_app_creds[service_name] = {
                    'id': app_cred.id,
                    'name': app_cred.name,
                    'secret': secret
                }

                # Save application credential to file for future use
                with open(f"{app_creds_dir}/{service_name}_app_cred.json", 'w') as f:
                    f.write(json.dumps(service_app_creds[service_name], indent=2))

                logger.info(f"Created application credential for {service_name} service: {app_cred_name}")

            except Exception as e:
                logger.error(f"Failed to create application credential for {service_name}: {e}")

    except Exception as e:
        logger.error(f"Failed to create application credentials: {e}")

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

    # Configure database
    configure_database_connection(config_path, 'neutron')

    # Re-read the config after configuration
    config = configparser.ConfigParser()
    config.read(config_path)

    # Configure Neutron to use application credentials
    configure_service_with_application_credential(config_path, 'neutron')

    # Check if we're using SQLite
    is_sqlite = False
    if 'database' in config and 'connection' in config['database']:
        db_connection = config['database']['connection']
        is_sqlite = 'sqlite' in db_connection.lower()
    else:
        # Assume SQLite if no connection string is specified
        is_sqlite = True

    # Handle database migrations
    if is_sqlite:
        logger.info("Using direct schema creation for Neutron with SQLite")

        # For SQLite, we'll create the schema directly instead of using migrations
        db_path = '/var/lib/openstack/neutron.sqlite'
        db_dir = os.path.dirname(db_path)
        os.makedirs(db_dir, exist_ok=True)

        # Create a Python script that directly creates the necessary tables
        # This avoids the SQLite ALTER TABLE limitations completely
        schema_script_path = '/tmp/create_neutron_schema.py'
        with open(schema_script_path, 'w') as f:
            f.write("""
import sys
import os
from oslo_config import cfg
from neutron.common import config
from neutron.db import models_base
from neutron.db.models import agent as agent_model
from neutron.db.models import allowedaddresspair as addr_pair_model
from neutron.db.models import external_net as ext_net_model
from neutron.db.models import l3 as l3_models
from neutron.db.models import l3_attrs as l3_attrs_models
from neutron.db.models import port as port_model
from neutron.db.models import port_security as psec
from neutron.db.models import rbac_db as rbac_models
from neutron.db.models import securitygroup as securitygroup_model
from neutron.db.models import segment as segment_model
from neutron.db.models import subnet as subnet_model
from neutron.db.models import tag as tag_model
from neutron.db.models import address_scope as address_scope_model
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic.migration import MigrationContext
from alembic import op

# Initialize the config
argv = ['--config-file', sys.argv[1]]
config.init(argv)
config.setup_logging()

# Get SQLite connection URL
conn_url = None
for conf_file in cfg.CONF.config_file:
    config_parser = cfg.ConfigParser(conf_file)
    if config_parser.has_section('database'):
        conn_url = config_parser.get('database', 'connection')
        if conn_url:
            break

if not conn_url:
    print("Database connection URL not found in config")
    sys.exit(1)

print(f"Using connection URL: {conn_url}")

# Create engine and tables
engine = create_engine(conn_url)
print("Creating Neutron tables...")

# Create tables for all models
models_base.BASEV2.metadata.create_all(engine)

# Create alembic version tables and stamp it to avoid migration errors
context = MigrationContext.configure(engine.connect())
if not engine.dialect.has_table(engine.connect(), 'alembic_version'):
    op._stamp_alembic_version = lambda revision, table=None: None
    op._update_current_rev = lambda from_, to_, table=None: None

    print("Creating alembic_version table")
    engine.execute('''
    CREATE TABLE alembic_version (
        version_num VARCHAR(32) NOT NULL,
        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
    )
    ''')

    # Insert current heads to avoid migration issues
    print("Stamping alembic_version with current heads")
    engine.execute("INSERT INTO alembic_version VALUES ('21eb2599b4d8')")  # expand head
    engine.execute("INSERT INTO alembic_version VALUES ('0e0a5c0abf5c')")  # contract head

print("Neutron database schema created successfully")
            """)

        try:
            # Execute the schema creation script
            logger.info("Creating Neutron schema directly with Python script")
            run_command(['python', schema_script_path, config_path])
            logger.info("Neutron database schema created successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create Neutron schema: {e}")
            logger.error("Neutron database migration failed. Services may not function correctly.")
    else:
        # For non-SQLite databases, use standard migration
        logger.info("Using standard migration strategy for Neutron with non-SQLite database")
        try:
            run_command(['neutron-db-manage', 'upgrade', 'head'])
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to sync Neutron database: {e}")
            logger.error("Neutron database migration failed. Services may not function correctly.")

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

    # Configure API and cell databases for SQLite compatibility
    if 'api_database' not in config:
        config['api_database'] = {}

    if 'sqlite' in config['database']['connection']:
        # If using SQLite for main DB, use SQLite for API DB too
        api_db_path = '/var/lib/openstack/nova_api.sqlite'
        config['api_database']['connection'] = f'sqlite:///{api_db_path}'
        logger.info(f"Using SQLite for Nova API database at {api_db_path}")
    else:
        # If using another DB type, ensure API DB is configured
        api_db_host = os.environ.get('NOVA_API_DB_HOST',
                               os.environ.get('NOVA_DB_HOST', 'localhost'))
        api_db_user = os.environ.get('NOVA_API_DB_USER', 'nova')
        api_db_pass = os.environ.get('NOVA_API_DB_PASSWORD', 'nova')
        api_db_name = os.environ.get('NOVA_API_DB_NAME', 'nova_api')

        if api_db_host == 'localhost' or 'sqlite' in config['database']['connection']:
            # For localhost, still use SQLite
            api_db_path = '/var/lib/openstack/nova_api.sqlite'
            config['api_database']['connection'] = f'sqlite:///{api_db_path}'
            logger.info(f"Using SQLite for Nova API database at {api_db_path}")
        else:
            # For external DB
            config['api_database']['connection'] = f'postgresql://{api_db_user}:{api_db_pass}@{api_db_host}/{api_db_name}'
            logger.info(f"Using PostgreSQL for Nova API database at {api_db_host}")

    # Write updated config
    with open(config_path, 'w') as f:
        config.write(f)

    # Check if using SQLite
    is_sqlite = 'sqlite' in config['database']['connection']

    try:
        # Handle Nova API database with SQLite compatibility
        if is_sqlite:
            logger.info("Using direct schema creation approach for Nova databases with SQLite")

            # Create a script to directly create Nova API DB schema
            nova_api_schema_script = '/tmp/create_nova_api_schema.py'
            with open(nova_api_schema_script, 'w') as f:
                f.write("""
import sys
import os
from oslo_config import cfg
from nova.cmd import manage
from nova import config
from nova import objects
from nova.objects import base as obj_base
from nova.db.api import models as api_models
from sqlalchemy import create_engine
from sqlalchemy.engine import reflection
from sqlalchemy.orm import sessionmaker

# Initialize the Nova config system
argv = ['--config-file', sys.argv[1]]
config.parse_args(argv)

# Get database connection from config
api_conn = cfg.CONF.api_database.connection

print(f"Using Nova API database connection: {api_conn}")

# Create engine and tables for API DB
api_engine = create_engine(api_conn)
print("Creating Nova API database tables...")
api_models.API_BASE.metadata.create_all(api_engine)

# Stamp API DB version to avoid migration issues
insp = reflection.Inspector.from_engine(api_engine)
if 'alembic_version' not in insp.get_table_names():
    print("Creating alembic_version table for API DB")
    api_engine.execute('''
    CREATE TABLE alembic_version (
        version_num VARCHAR(32) NOT NULL,
        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
    )
    ''')
    # Add current head revision
    api_engine.execute("INSERT INTO alembic_version VALUES ('9c5d796f1b85')")

print("Nova API database schema created successfully")
                """)

            # Execute Nova API schema creation script
            run_command(['python', nova_api_schema_script, config_path])
            logger.info("Nova API database schema created successfully")

            # Create a script to directly create Nova main DB schema
            nova_main_schema_script = '/tmp/create_nova_main_schema.py'
            with open(nova_main_schema_script, 'w') as f:
                f.write("""
import sys
import os
from oslo_config import cfg
from nova.cmd import manage
from nova import config
from nova import objects
from nova.objects import base as obj_base
from nova.db.main import models as main_models
from nova.db import types
from sqlalchemy import create_engine
from sqlalchemy.engine import reflection

# Initialize the Nova config system
argv = ['--config-file', sys.argv[1]]
config.parse_args(argv)

# Get database connection from config
main_conn = cfg.CONF.database.connection

print(f"Using Nova main database connection: {main_conn}")

# Create engine and tables for main DB
main_engine = create_engine(main_conn)
print("Creating Nova main database tables...")
main_models.BASE.metadata.create_all(main_engine)

# Stamp main DB version to avoid migration issues
insp = reflection.Inspector.from_engine(main_engine)
if 'alembic_version' not in insp.get_table_names():
    print("Creating alembic_version table for main DB")
    main_engine.execute('''
    CREATE TABLE alembic_version (
        version_num VARCHAR(32) NOT NULL,
        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
    )
    ''')
    # Add current head revision
    main_engine.execute("INSERT INTO alembic_version VALUES ('8f2f1571d55b')")

# Create cell0 database
cell0_conn = main_conn.replace('nova.sqlite', 'nova_cell0.sqlite')
print(f"Creating Nova cell0 database at {cell0_conn}")
cell0_engine = create_engine(cell0_conn)
main_models.BASE.metadata.create_all(cell0_engine)

# Stamp cell0 DB version
insp = reflection.Inspector.from_engine(cell0_engine)
if 'alembic_version' not in insp.get_table_names():
    print("Creating alembic_version table for cell0 DB")
    cell0_engine.execute('''
    CREATE TABLE alembic_version (
        version_num VARCHAR(32) NOT NULL,
        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
    )
    ''')
    # Add current head revision
    cell0_engine.execute("INSERT INTO alembic_version VALUES ('8f2f1571d55b')")

# Create cell mappings in API DB
if 'cell_mappings' in insp.get_table_names() and not main_engine.execute("SELECT * FROM cell_mappings").fetchall():
    print("Creating cell mappings")
    main_engine.execute(f'''
    INSERT INTO cell_mappings (uuid, name, transport_url, database_connection, created_at, updated_at, disabled)
    VALUES ('00000000-0000-0000-0000-000000000000', 'cell0', 'none:///cell0', '{cell0_conn}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
    ''')

    main_engine.execute(f'''
    INSERT INTO cell_mappings (uuid, name, transport_url, database_connection, created_at, updated_at, disabled)
    VALUES ('11111111-1111-1111-1111-111111111111', 'cell1', 'rabbit://guest:guest@localhost:5672/', '{main_conn}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
    ''')

print("Nova main database schema created successfully")
                """)

            # Execute Nova main schema creation script
            run_command(['python', nova_main_schema_script, config_path])
            logger.info("Nova main database schema created successfully")

        else:
            # Run standard Nova DB sync for non-SQLite databases
            logger.info("Using standard migration for Nova with non-SQLite database")
            run_command(['nova-manage', 'api_db', 'sync'])
            run_command(['nova-manage', 'cell_v2', 'map_cell0'])
            run_command(['nova-manage', 'cell_v2', 'create_cell', '--name=cell1', '--verbose'])
            run_command(['nova-manage', 'db', 'sync'])

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to sync Nova database: {e}")
        logger.error("Nova database migration failed. Services may not function correctly.")

    logger.info("Nova configuration complete")

def configure_horizon():
    """Configure Horizon dashboard"""
    logger.info("Configuring Horizon")

    # Create local_settings.py with correct configuration
    settings_path = '/etc/openstack-dashboard/local_settings.py'

    # Check if horizon application credential exists
    app_cred_file = '/var/lib/openstack/app_credentials/horizon_app_cred.json'
    horizon_app_cred = None
    if (os.path.exists(app_cred_file)):
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

# ASGI configuration for Django
ASGI_APPLICATION = 'openstack_dashboard.asgi.application'
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

def start_services():
    """Start all OpenStack services using a unified Starlette app with Gunicorn+UvicornWorker"""
    logger.info("Starting OpenStack services")

    # Create unified ASGI application for web services
    unified_app = create_unified_openstack_app()

    # Calculate optimal number of workers based on CPU cores
    workers = (multiprocessing.cpu_count() * 2) + 1
    logger.info(f"Using {workers} workers for Gunicorn servers")

    # Start unified API Gateway with Gunicorn+UvicornWorker (port 80)
    logger.info("Starting unified OpenStack API Gateway with Gunicorn+UvicornWorker")
    # Create a temporary Python module that imports the app
    unified_module_path = '/tmp/openstack_app.py'
    with open(unified_module_path, 'w') as f:
        f.write("""
# Unified OpenStack ASGI application module for Gunicorn
import os
import sys
import logging
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.responses import PlainTextResponse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openstack-unified")

# Fallback handler for the root path
async def homepage(request):
    return PlainTextResponse("OpenStack Unified API Gateway")

# Create individual service apps

# Keystone (Identity) app
try:
    # First try native ASGI
    try:
        from keystone.server import asgi as keystone_asgi
        keystone_app = keystone_asgi.application
        logger.info("Using native Keystone ASGI application")
    except ImportError:
        # Fallback to WSGI adapter
        from asgiref.wsgi import WsgiToAsgiMiddleware
        from keystone.server import wsgi as keystone_wsgi
        keystone_app = WsgiToAsgiMiddleware(keystone_wsgi.application)
        logger.info("Using WSGI-to-ASGI adapter for Keystone")
except Exception as e:
    logger.error(f"Failed to create Keystone app: {e}")
    async def keystone_fallback(scope, receive, send):
        await send({
            'type': 'http.response.start',
            'status': 503,
            'headers': [[b'content-type', b'text/plain']],
        })
        await send({
            'type': 'http.response.body',
            'body': b'Keystone Identity service unavailable',
        })
    keystone_app = keystone_fallback

# Horizon (Dashboard) app
try:
    import django
    from django.core.asgi import get_asgi_application
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openstack_dashboard.settings')
    django.setup()
    horizon_app = get_asgi_application()
    logger.info("Using native Django ASGI for Horizon")
except Exception as e:
    logger.error(f"Failed to create Horizon app: {e}")
    async def horizon_fallback(scope, receive, send):
        await send({
            'type': 'http.response.start',
            'status': 503,
            'headers': [[b'content-type', b'text/plain']],
        })
        await send({
            'type': 'http.response.body',
            'body': b'Horizon Dashboard service unavailable',
        })
    horizon_app = horizon_fallback

# Create mounts for each service with their standard URL paths
service_paths = {
    'keystone': '/identity',
    'horizon': '/',  # Dashboard at root
}

routes = [
    Mount(service_paths['keystone'], app=keystone_app),
    Mount(service_paths['horizon'], app=horizon_app),
]

# Create the unified Starlette app with all routes
application = Starlette(debug=False, routes=routes)
""")

    unified_cmd = [
        'gunicorn',
        '--bind', '0.0.0.0:80',
        '--workers', str(workers),
        '--worker-class', 'uvicorn.workers.UvicornWorker',
        '--timeout', '120',
        '--access-logfile', '-',
        '--error-logfile', '-',
        'openstack_app:application'
    ]
    unified_process = subprocess.Popen(unified_cmd)

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
            if unified_process.poll() is not None:
                logger.error("Unified OpenStack server exited unexpectedly")
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
        unified_process.terminate()
        glance_api_process.terminate()
        cinder_api_process.terminate()
        neutron_process.terminate()
        ironic_api_process.terminate()
        nova_api_process.terminate()
        nova_conductor_process.terminate()
        nova_scheduler_process.terminate()
        nova_compute_process.terminate()

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
    Initialize Keystone fernet keys for token encryption without relying on external commands
    """
    logger.info("Initializing Keystone fernet keys")

    # Fernet keys for tokens
    fernet_keys_dir = '/etc/keystone/fernet-keys'
    os.makedirs(fernet_keys_dir, exist_ok=True)

    # Create initial fernet key (key 0)
    key_0_path = os.path.join(fernet_keys_dir, '0')
    if not os.path.exists(key_0_path):
        try:
            # Generate a fernet key using cryptography
            key = Fernet.generate_key()
            with open(key_0_path, 'wb') as f:
                f.write(key)
            logger.info("Keystone fernet keys created successfully")
        except Exception as e:
            logger.error(f"Failed to create Keystone fernet key: {e}")
            # Create a minimal key manually if that fails
            with open(key_0_path, 'w') as f:
                f.write('c_7Q3FIUcWR7vJUMgCJ42CWpV8s_Q27wnXP91c3-fc=')
            logger.info("Created a fallback fernet key manually")

    # Credential keys
    credential_keys_dir = '/etc/keystone/credential-keys'
    os.makedirs(credential_keys_dir, exist_ok=True)

    # Create initial credential key
    cred_key_0_path = os.path.join(credential_keys_dir, '0')
    if not os.path.exists(cred_key_0_path):
        try:
            # Generate a credential key
            key = Fernet.generate_key()
            with open(cred_key_0_path, 'wb') as f:
                f.write(key)
            logger.info("Keystone credential keys created successfully")
        except Exception as e:
            logger.error(f"Failed to create Keystone credential key: {e}")
            # Create a minimal key manually if that fails
            with open(cred_key_0_path, 'w') as f:
                f.write('c_7Q3FIUcWR7vJUMgCJ42CWpV8s_Q27wnXP91c3-fc=')
            logger.info("Created a fallback credential key manually")

    # Set proper permissions
    for directory in [fernet_keys_dir, credential_keys_dir]:
        for root, dirs, files in os.walk(directory):
            for f in files:
                os.chmod(os.path.join(root, f), 0o600)  # Secure permissions for keys

    logger.info("Keystone encryption keys initialized")

def create_keystone_asgi_app():
    """
    Create an ASGI application for Keystone
    """
    logger.info("Creating ASGI application for Keystone")

    try:
        # Try to import the keystone ASGI application if available
        # First check if Keystone has native ASGI support
        try:
            from keystone.server import asgi as keystone_asgi
            asgi_app = keystone_asgi.application
            logger.info("Using native Keystone ASGI application")
            return asgi_app
        except ImportError:
            logger.warning("Native Keystone ASGI not available, creating custom ASGI app")

        # If native support is not available, create a simple ASGI app that
        # forwards requests to the WSGI application using an adapter
        from asgiref.wsgi import WsgiToAsgiMiddleware
        from keystone.server import wsgi as keystone_wsgi

        wsgi_app = keystone_wsgi.application
        asgi_app = WsgiToAsgiMiddleware(wsgi_app)
        logger.info("Created ASGI adapter for Keystone WSGI application")
        return asgi_app

    except Exception as e:
        logger.error(f"Failed to create Keystone ASGI application: {e}")

        # As a fallback, create a minimal ASGI app that serves a 503 response
        async def fallback_app(scope, receive, send):
            if scope['type'] == 'http':
                await send({
                    'type': 'http.response.start',
                    'status': 503,
                    'headers': [
                        [b'content-type', b'text/plain'],
                    ]
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'Keystone service unavailable',
                })

        logger.warning("Using fallback ASGI application for Keystone")
        return fallback_app

def create_horizon_asgi_app():
    """
    Create a native ASGI application for Horizon using Django's ASGI support
    """
    logger.info("Creating native ASGI application for Horizon")

    try:
        # Import Django's ASGI application
        import django
        from django.core.asgi import get_asgi_application

        # Set Django settings module
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openstack_dashboard.settings')
        django.setup()

        # Get the native ASGI application
        asgi_app = get_asgi_application()
        logger.info("Successfully created ASGI application for Horizon")
        return asgi_app

    except Exception as e:
        logger.error(f"Failed to create Horizon ASGI application: {e}")

        # As a fallback, create a minimal ASGI app that serves a 503 response
        async def fallback_app(scope, receive, send):
            if scope['type'] == 'http':
                await send({
                    'type': 'http.response.start',
                    'status': 503,
                    'headers': [
                        [b'content-type', b'text/plain'],
                    ]
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'Horizon dashboard unavailable',
                })

        logger.warning("Using fallback ASGI application for Horizon")
        return fallback_app

def create_unified_openstack_app():
    """
    Create a unified Starlette application that mounts all OpenStack services
    at their appropriate URLs following the DevStack/standard OpenStack path conventions
    """
    logger.info("Creating unified OpenStack ASGI application")

    # Create a base Starlette application
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.responses import PlainTextResponse

    # Fallback handler for the root path
    async def homepage(request):
        return PlainTextResponse("OpenStack Unified API Gateway")

    # Dictionary mapping OpenStack services to their default URL prefixes
    service_paths = {
        'keystone': '/identity',
        'glance': '/image',
        'cinder': '/volume',
        'nova': '/compute',
        'neutron': '/network',
        'ironic': '/baremetal',
        'placement': '/placement',
        'horizon': '/',  # Dashboard at root
    }

    # Create individual ASGI apps

    # Keystone (Identity) app
    try:
        # First try native ASGI
        try:
            from keystone.server import asgi as keystone_asgi
            keystone_app = keystone_asgi.application
            logger.info("Using native Keystone ASGI application")
        except ImportError:
            # Fallback to WSGI adapter
            from asgiref.wsgi import WsgiToAsgiMiddleware
            from keystone.server import wsgi as keystone_wsgi
            keystone_app = WsgiToAsgiMiddleware(keystone_wsgi.application)
            logger.info("Using WSGI-to-ASGI adapter for Keystone")
    except Exception as e:
        logger.error(f"Failed to create Keystone app: {e}")
        async def keystone_fallback(scope, receive, send):
            await send({
                'type': 'http.response.start',
                'status': 503,
                'headers': [[b'content-type', b'text/plain']],
            })
            await send({
                'type': 'http.response.body',
                'body': b'Keystone Identity service unavailable',
            })
        keystone_app = keystone_fallback

    # Horizon (Dashboard) app
    try:
        import django
        from django.core.asgi import get_asgi_application
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openstack_dashboard.settings')
        django.setup()
        horizon_app = get_asgi_application()
        logger.info("Using native Django ASGI for Horizon")
    except Exception as e:
        logger.error(f"Failed to create Horizon app: {e}")
        async def horizon_fallback(scope, receive, send):
            await send({
                'type': 'http.response.start',
                'status': 503,
                'headers': [[b'content-type', b'text/plain']],
            })
            await send({
                'type': 'http.response.body',
                'body': b'Horizon Dashboard service unavailable',
            })
        horizon_app = horizon_fallback

    # Create mounts for each service
    routes = [
        Mount(service_paths['keystone'], app=keystone_app),
        Mount(service_paths['horizon'], app=horizon_app),
    ]

    # Create the unified Starlette app with all routes
    app = Starlette(debug=False, routes=routes)

    logger.info("Unified OpenStack ASGI application created")
    return app

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
