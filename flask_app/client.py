import requests
import googlemaps
import re
import datetime
import dateutil
    
class api(object):
    def __init__(self, api_key):
        self.session = requests.Session()
        self.key = api_key
        self.client = googlemaps.Client(self.key)
        self.routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        self.routes_header = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': self.key,
            'X-Goog-FieldMask': 'routes.legs.steps.transitDetails'
        }
    
    """
    uses google maps python api to find address data for a place input as a string,
    returns the address from the response, if an error occurs, prints code and message
    associated with the error type
    """
    
    # build in error handling for invalid locations
    def get_addr(self, location):
        query = f'Closest WMATA Metro Station to {location}'
        response = self.client.find_place(input=query, 
                                          input_type='textquery', 
                                          fields=['formatted_address','name','types'])
        if "error" in response:
            code = response["error"]["code"]
            msg = response["error"]["message"]
            return f'Code:{code}, Error Message: {msg}'
        
        return response['candidates'][0]['formatted_address']
        
    """
    desc: 
        queries a route from the google routes api between point start and point end,
        if an error occurs, prints the code and message associated with the error type,
        otherwise, returns a list of transit directions
    params:
        start: desired origin <string>
        end: desired destination <string>
        departure_t: time to depart <datetime.datetime>
    """
    def compute_route(self, start, end, departure_t):
        
        # get addresses of start and end
        origin_addr = self.get_addr(location=start)
        dest_addr = self.get_addr(location=end)
        
        # convert datetime to ZULU UTC format
        new_hour = 0
        new_minute = 0
        
        # UTC
        if departure_t.hour + 4 >= 24:
            new_hour = departure_t.hour + 4 - 24
        else:
            new_hour = departure_t.hour + 4

        # for some reason it has a 30 minute buffer, remove that buffer
        if departure_t.minute - 30 < 0:
            new_minute = departure_t.minute - 30 + 60
            new_hour = new_hour - 1
        else:
            new_minute = departure_t.minute - 30
            
        zulu_timestr = f'{departure_t.year}-{departure_t.month}-{departure_t.day}T{new_hour:02}:{new_minute:02}:00Z'
        
        # extra parameters for query
        data = {
            "origin" : {
                "address": origin_addr
            },
            "destination": {
                "address": dest_addr
            },
            'travelMode': "TRANSIT",
            'departureTime': zulu_timestr,
            'transitPreferences': {
                'allowedTravelModes': ["SUBWAY", "TRAIN"]
            }
        }
        
        # request
        response = requests.post(url=self.routes_url, headers=self.routes_header, json=data)
        
        if "error" in response:
            code = response["error"]["code"]
            msg = response["error"]["message"]
            return f'Code:{code}, Error Message:{msg}'
    
        # converts json to dictionary, filters for transit steps
        resp_as_dict = response.json()
        filtered = filter((lambda x: x), resp_as_dict['routes'][0]['legs'][0]['steps'])
        
        # list of information about each step of transit route, list is in step order
        route_info = []
        time_pattern = re.compile("([0-9]{1,2}):([0-9]{2}).*(AM|PM).*")
        
        for step in filtered:
            matched_dpt = re.fullmatch(time_pattern, 
                                       step['transitDetails']['localizedValues']['departureTime']['time']['text'])
            matched_arr = re.fullmatch(time_pattern,
                                       step['transitDetails']['localizedValues']['arrivalTime']['time']['text'])
            
            dpt_hr = int(matched_dpt.group(1))
            dpt_min = int(matched_dpt.group(2))
            dpt_meridiem = matched_dpt.group(3)
            
            arr_hr = int(matched_arr.group(1))
            arr_min = int(matched_dpt.group(2))
            arr_meridiem = matched_arr.group(3)
            
            if dpt_meridiem == "PM":
                dpt_hr += 12
            
            # add 5 min walking buffer to arrival time
            if arr_min + 5 >= 60:
                arr_min = arr_min - 60 + 5
                arr_hr += 1
                
            if arr_meridiem == "PM":
                if arr_hr + 12 >= 24:
                    arr_hr = arr_hr + 12 - 24
                else:
                    arr_hr += 12
            
            route_info.append({
                'line_info': {
                    "line": step['transitDetails']['transitLine']['name'],
                    'hex_color': step['transitDetails']['transitLine']['color'],
                    "headsign": step['transitDetail']['headsign']
                },
                "from": {
                    "name": step['transitDetails']['stopDetails']['departureStop']['name'],
                    'est_dept_t': datetime.time(dpt_hr, dpt_min)        
                },
                "to": {
                    "name": step['transitDetails']['stopDetails']['arrivalStop']['name'],
                    'est_arr_t': datetime.time(arr_hr, arr_min)
                }
            })
        
        # returns a list of the filtered non-empty transit steps with necessary information
        return route_info


# testing route computation stuff
# dotenv.load_dotenv()
# client = api(os.getenv('GOOG_API_KEY'))
# client.compute_route('Wiehle Avenue', 'University of Maryland, College Park', datetime.datetime.now())
# time_pattern = re.compile("([0-9]{1,2}):([0-9]{2}).*(AM|PM).*")

# matched_arr = re.fullmatch(time_pattern, '11:59\u202f''PM')

# arr_hr = int(matched_arr.group(1))
# arr_min = int(matched_arr.group(2))
# arr_meridiem = matched_arr.group(3)

# if arr_min + 5 >= 60:
#     arr_min = arr_min - 60 + 5
#     arr_hr += 1
    
# if arr_meridiem == "PM":
#     if arr_hr + 12 >= 24:
#         arr_hr = arr_hr + 12 - 24
#     else:
#         arr_hr += 12
    
# print(f"{arr_hr:02}:{arr_min:02}")

# takes time as HH:MM

# local json processing stuff
# with open(r"dump.json", "w", encoding="utf-8") as f:
#     json.dump(resp.json(), f, ensure_ascii=False, indent=4)
# with open(r"dump.json", "r") as f:
#     resp = json.load(f)
    
# notes about testing:
# need to convert local time to UTC for zulu fmt
# for some reason the departure time calculation has a random 30 minute buffer built in??
