# flight_tracker/fetch.py
import requests
import configparser
from flight_tracker.utils import logger

BASE_URL = "https://opensky-network.org/api/states/all"
CONFIG_PATH = '/root/.config/pyopensky/settings.conf'

# Load OpenSky credentials
config = configparser.ConfigParser()
try:
    config.read(CONFIG_PATH)
    USERNAME = config['opensky']['username']
    PASSWORD = config['opensky']['password']
except KeyError as e:
    logger.error(f"Missing OpenSky credentials in {CONFIG_PATH}: {e}")
    raise
except Exception as e:
    logger.error(f"Failed to read config file {CONFIG_PATH}: {e}")
    raise

credits_used = 0
MAX_CREDITS = 4000  # Daily credit limit

def calculate_credit_cost(lamin, lamax, lomin, lomax):
    """
    Calculate the credit cost based on the area size.
    
    Args:
        lamin, lamax, lomin, lomax (float): Bounding box coordinates.
    
    Returns:
        int: Credit cost for the API call.
    """
    area = (lamax - lamin) * (lomax - lomin)
    if area <= 25:
        return 1
    elif area <= 100:
        return 2
    elif area <= 400:
        return 3
    else:
        return 4

def fetch_flight_data(area):
    """
    Fetch flight states from OpenSky Network API for a given monitored area.
    
    Args:
        area (MonitoredArea): The area to fetch data for.
    
    Returns:
        dict or None: API response data or None if fetch fails or credits exceeded.
    """
    global credits_used
    cost = calculate_credit_cost(area.lamin, area.lamax, area.lomin, area.lomax)
    
    if credits_used + cost > MAX_CREDITS:
        logger.warning(f"Credit limit reached ({credits_used}/{MAX_CREDITS}). Skipping fetch for area {area.id}")
        return None
    
    params = {
        "lamin": area.lamin,
        "lamax": area.lamax,
        "lomin": area.lomin,
        "lomax": area.lomax
    }
    
    try:
        response = requests.get(BASE_URL, params=params, auth=(USERNAME, PASSWORD), timeout=30)
        response.raise_for_status()
        states = response.json()
        
        if not states or 'states' not in states or states['states'] is None:
            logger.warning(f"Invalid API response for area {area.id}: {states}")
            return None
        
        states_count = len(states['states'])
        logger.info(f"Fetched {states_count} states for area {area.id}")
        
        # Validate state data
        valid_states = []
        for state in states['states']:
            if not all(isinstance(state[i], (int, float, str, type(None))) for i in [0, 5, 6, 7, 9]):
                logger.warning(f"Invalid state data for flight {state[0]}: {state}")
            else:
                valid_states.append(state)
        states['states'] = valid_states
        
        credits_used += cost
        logger.info(f"Credits used: {credits_used}/{MAX_CREDITS}")
        return states
    
    except requests.RequestException as e:
        logger.error(f"Failed to fetch data for area {area.id}: {e}")
        return None