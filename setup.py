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
            ee.Authenticate(force=True)
            ee.Initialize(project=project)
            print('Initialize completed')
            return project
         else:
            return None
    except Exception as e:
        print(f"Error initializing Earth Engine: {e}")