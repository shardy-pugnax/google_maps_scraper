  """
Sam Hardy

Scrape Google Maps for drivetimes, no need for fancy API's or paid subscriptions!

This script (gmaps_traffic_scraper.py) and all other supporting files 
(bay_area_lats_longs.json, traffic_table.csv) will/should be in the same directory 
in order to run properly.
"""

import requests
import re
import json
from datetime import date, datetime
import calendar
import pandas as pd
import os
import csv
import time

    
def get_distance_and_time(start_latlong: list, end_latlong: list) -> dict:
    """
    This function calculates the current real-time driving distance and time
    between two point (latitude longitude) on Google maps.  It will only look
    for driving (car) routes.
    
    First, tried searching for:
    You are on the fastest route.\"],[\"You should arrive around 3:48 PM.\",1]],[60]
    But that only worked sometimes.
    
    More robust turns out to be:
    Search for keyword 'miles' and parse out the route options from that.
    
    Input: starting latitude and longitude, ending latitude and longitude
    Output: dictionary of route options, along with cooresponding distance and time
    
    TODO: Refactor on a rainy day.
    
    """

    start_lat = start_latlong[0]
    start_long = start_latlong[1]
    end_lat = end_latlong[0]
    end_long = end_latlong[1]
    
    url = f'https://www.google.com/maps/dir/{start_lat},{start_long}/{end_lat},{end_long}'
    
    # print(url) # sanity check that data is being pulled from Google Maps correctly.  Only uncomment for debugging purposes.
    
    resp = requests.get(url) # pull useful info from source code
    bigmash = resp.text # a big ugly mess that has all the info, but badly needs parsing!
    
    # seperate out different route options.
    miles_idx = [m.start() for m in re.finditer('miles', bigmash)]
    route_options_list = [bigmash[idx-50:idx+1300] for idx in miles_idx] # Conservatively capture all useful info
    
    # print(route_options_list)
    # print(bigmash)
    
    route_option = 1
    route_dict = {}
    for route in route_options_list:
        
        # reject routes that use public transit, like a true American!
        if 'every' in route or 'Ticket' in route or '$' in route or 'Walk' in route or 'Transit' in route or 'Train' in route:
            continue
        
        # handle the corner case of an accidnt--convert long travel time route (with hour units) to minutes in order to be standardized units of time
        if 'hr' in route:
            pass
        
        # find the distance
        ai = route.find('miles\\')
        for j in range(10):
            if route[ai-j] == '"':
                distance = float(route[ai-j+1:ai].strip())
                break
        
        # find the meaningful time (worst-case of all the options listed), and make sure it's real based on current real-time conditions
        timeminutes_alot = []
        bi = [m.start() for m in re.finditer('min\\\\', route)]
        for g in bi:
            for h in range(10):
                if route[g-h] == '"':

                    # Added new code to handle GMaps recent changes
                    a = route[g-h+1:g].strip()
                    if '–' not in a: # it's not a - dash, but a different weird character!
                        timeminutes_alot.append(route[g-h+1:g].strip())
                        break
        timeminutes_alot1 = []
        for item in timeminutes_alot:
            if "-" not in item:
                if 'hr' in item:
                    h, m = item.split('hr')
                    time_m = int(h.strip()) * 60 + int(m.strip())
                else:
                    time_m = item
                        
                timeminutes_alot1.append(int(time_m))
        
        timeminutes = max(timeminutes_alot1)
        
        route_dict[str(f'route_{route_option}_distance_miles')] = distance
        route_dict[str(f'route_{route_option}_time_minutes')] = timeminutes
        
        route_option = route_option + 1
        
    # add a few dummy route option placeholders, to account for future runs of this script having more additional route options
    route_dict[str(f'route_{route_option}_distance_miles')] = ''
    route_dict[str(f'route_{route_option}_time_minutes')] = ''
    route_dict[str(f'route_{route_option + 1}_distance_miles')] = ''
    route_dict[str(f'route_{route_option + 1}_time_minutes')] = ''
    
    # print('\n--------ROUTE START-------------\n', route, '\n----------ROUTE END-----------\n') # sanity check that data is being pulled from Google Maps correctly.  Only uncomment for debugging purposes.
    
    return route_dict



def get_coords(json_filepath):
    with open(json_filepath, 'r') as f:
        data = json.load(f)
    return data


def get_current_time():
    now = {}
    
    curr_date = date.today()
    dayofweek = calendar.day_name[curr_date.weekday()]
    timeampm = datetime.today().strftime("%I:%M %p")
    
    timeampm_minute = datetime.today().minute
    timeampm_hour = datetime.today().hour
    if timeampm_minute < 15:
        timeampm_round = '00'
    elif timeampm_minute >= 15 and timeampm_minute < 45:
        timeampm_round = '30'
    elif timeampm_minute >= 45:
        timeampm_round = '00'
        timeampm_hour += 1
    if timeampm_hour < 12:
        ampm = 'AM'
    else:
        ampm = 'PM'
        timeampm_hour -= 12
        
    timeampm_round = str(timeampm_hour) + ':' + str(timeampm_round) + ' ' + ampm
    
    now['date'] = str(curr_date)
    now['dayofweek'] = dayofweek
    now['time'] = timeampm
    now['time_halfhour'] = timeampm_round
    
    return now


def write_or_append_to_csv(d: dict):
    '''
    Write/append results to a csv file, for later analysis or visualization (like with JMP)
    '''

    path = r'traffic_table_results.csv'

    if os.path.isfile(path):
        
        pddf = pd.DataFrame([d])
        pddf.to_csv(path, mode='a', index=False, header=False)
        
    else:
        
        pddf = pd.DataFrame([d])
        pddf.to_csv(path, index=False)


def downselect_optimal_t_route(d: dict) -> dict:
    '''
    Takes a full results dictionary (with multiple distance/time routes), and keeps only the best cooresponding time.
    Reason for this is to standardize results table, and avoid any potential formatting errors
    '''

    routes_t = {key: d[key] for key in d.keys() if '_time_minutes' in key and not d[key] == ''}

    routes_d = {key: d[key] for key in d.keys() if '_distance_miles' in key and not d[key] == ''}

    min_t = min(routes_t.values())
    lrk = list(routes_t.keys())
    lrv = list(routes_t.values())
    mrt = [lrk[i].strip('_time_minutes') for i in range(len(lrk)) if lrv[i] == min_t]

    # If a tie for minimum time, just pick the shortest distance then
    mrt_d_options = {}
    for r in mrt:
        mrt_d_options.update(dict(filter(lambda item: r in item[0], routes_d.items())))

    mrt_d = min(mrt_d_options.keys(), key=(lambda k: mrt_d_options[k])).strip('_distance_miles')

    # Now remove the non-optimized route options
    d_opt = {}
    for key in d.keys():
        new_key = key
        if ('_time_minutes' in key or '_distance_miles' in key):
            if mrt_d not in key:
                continue
            if '_time_minutes' in key:
                new_key = 'optimal_drive_time_minutes'
            elif '_distance_miles' in key:
                new_key = 'optimal_drive_distance_miles'
        d_opt[new_key] = d[key]

    return d_opt


if __name__ == '__main__':
    
    # Depending on speed / interest, choice for single pre-defined ping, or multiple pre-defined pings
    SINGLE_PING = 0
    MULTI_PING = 1
    
    print('Writing to CSV file...')

    # Added in program runtime diagnostics
    t0 = time.time()
    elapsed = time.time() - t0
    
    coords = get_coords('bay_area_lats_longs.json') # Reference bay area landmarks. Careful--if too many risk hitting the reCAPTCHA :(
    
    if SINGLE_PING:
        
        start_point = '49er Stadium'
        end_point = 'Palo Alto'
    
        dt = get_distance_and_time(coords[start_point], coords[end_point])
    
        timestamp = get_current_time()
    
        route = {}
        route['route'] = start_point + '_to_' + end_point
    
        results = {**route, **dt, **timestamp}
        results_opt = downselect_optimal_t_route(results)
    
        write_or_append_to_csv(results_opt)
    
    if MULTI_PING:
        
        start_coords = list(coords.keys())
        
        for start_coord in start_coords:
            
            end_coords = start_coords[:]
            end_coords.remove(start_coord)
            
            for end_coord in end_coords:
                
                start_point = start_coord
                end_point = end_coord
                
                dt = get_distance_and_time(coords[start_point], coords[end_point])
                
                timestamp = get_current_time()
                
                route = {}
                route['route'] = start_point + '_to_' + end_point
                
                results = {**route, **dt, **timestamp}
                results_opt = downselect_optimal_t_route(results)

                print(f"Publishing analysis of {route['route']}...")
                write_or_append_to_csv(results_opt)
                
                # Attempting to workaround the CAPTCHA rate-limiter.  ie don't ping too frequently or a flag will be raised :(
                time.sleep(10)

    # Added in program runtime diagnostics
    elapsed = time.time() - t0

    print(f'CSV writing done, program complete in {elapsed} seconds!')
