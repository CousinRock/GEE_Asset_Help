import ee
import geemap
import os

def initialize_earth_engine():
    """
    Initialize the Earth Engine API.
    """
    try:
         project = os.environ.get("PROJECT")
         if project:
            print(f"Project: {project}")
            # geemap.set_proxy(port=20171)
            ee.Authenticate()
            ee.Initialize(project=project)

            return project
         else:
            return None
    except Exception as e:
        print(f"Error initializing Earth Engine: {e}")