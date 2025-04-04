#!/usr/bin/env python3
import sys
import urllib.request
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('openstack-healthcheck')

def check_health():
    """
    Check the health of the OpenStack container by querying the /healthz endpoint
    """
    try:
        logger.info("Performing health check")
        with urllib.request.urlopen("http://localhost/healthz") as response:
            if response.getcode() != 200:
                logger.error(f"Health check failed with status code: {response.getcode()}")
                return False

            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") != "healthy":
                logger.error(f"Health check returned unhealthy status: {data}")
                return False

            # Check individual services if they're reported
            if "services" in data:
                for service, status in data.get("services", {}).items():
                    if isinstance(status, dict) and status.get("status") != "running":
                        logger.warning(f"Service {service} is not running: {status}")
                    elif isinstance(status, str) and status != "running":
                        logger.warning(f"Service {service} is not running: {status}")

            logger.info("Health check passed")
            return True
    except Exception as e:
        logger.error(f"Health check failed with exception: {e}")
        return False

if __name__ == "__main__":
    if check_health():
        sys.exit(0)
    else:
        sys.exit(1)
