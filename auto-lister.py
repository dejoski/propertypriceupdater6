#%%
import datetime
import json
import re
import sys
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from sqlalchemy import create_engine
from datetime import date, timedelta
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.utils import ChromeType



from seleniumrequests import Chrome



db_connection_str = 'mysql+pymysql://propertypriceupdater6:propertypriceupdater@72.167.68.58/AirBnB_CashCow'
print("---LOADED AUTOBOOKER---")



def build_dates(days = 90):
    d = datetime.datetime.today()
    dates = []
    for x in range(days):
        d += timedelta(days = 1)  # First Sunday
        dates.append(d.strftime('%Y-%m-%d'))
    return dates


while True:
    days = 90
    dates = build_dates(days)

    db_connection = create_engine(db_connection_str)

    Config_DF = pd.read_sql('SELECT * FROM Config', con=db_connection)
    # Config_DF = Config_DF[Config_DF["PartnerID"]=='CozyStays']
    # Config_DF = Config_DF[Config_DF["hosttools_listingID"]=='6103b4abbc2d884c8a1f9881']
    #do not loop listing but instead get the oldest every time


    valid_configs = Config_DF[Config_DF["Updated_At"]!='Soon']
    valid_configs["Updated_At"] = valid_configs["Updated_At"].str.replace('Failed at ','')
    valid_configs["Updated_At"] = pd.to_datetime(valid_configs["Updated_At"])
    max_date = valid_configs["Updated_At"].max()
    listing = valid_configs[valid_configs["Updated_At"]!=max_date].sort_values(by='Updated_At',na_position='first').iloc[0,:]

    options = webdriver.ChromeOptions()    
    options.add_argument('--headless')
    options.add_argument('--no-sandbox') 
    options.add_argument("start-maximized")
    options.add_argument("enable-automation")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-browser-side-navigation")
    options.add_argument("--disable-gpu")

    logged_into_hosttools = False
    logged_into_roomsteals = False
    try:
        driver = Chrome(ChromeDriverManager().install(),chrome_options=options)

        # driver.set_page_load_timeout(30000)
        if not logged_into_roomsteals:
            driver.get("https://roomsteals.com/login")

            driver.find_element_by_id('email').send_keys("main@handsfreeservices.com")
            driver.find_element_by_id('password').send_keys("HFAuto0912$")
            driver.find_element_by_id('submit').click()
            logged_into_roomsteals = True

        hosttools_listingID = listing["hosttools_listingID"]
        increase_by = listing["increase_by"]
        Rooms = listing["Rooms"]
        hotel_name = listing["hotel_name"]
        Bed_Filter = listing["Bed_Filter"]
        timezone = listing["timezone"]
        Roomsteals_ID = listing["Roomsteals_ID"]

            
        db_connection = create_engine(db_connection_str)
        conn = db_connection.connect()
        result = db_connection.execute("update Config set Updated_At = 'Soon' where hosttools_listingID='"+hosttools_listingID+"'")
        if not Roomsteals_ID:
            time.sleep(1)
            hotel_name_response = driver.request('GET','https://roomsteals.com/findplacefromtext/'+hotel_name).json()

            name = hotel_name_response["name"]
            formatted_address = hotel_name_response["formatted_address"]

            api_call = driver.request('GET',"https://roomsteals.com/hotels/find-rate?address="+formatted_address+"&inDate="+dates[0]+"&outDate="+dates[1]+"&rooms=1&adults=3&children=0&currency=USD&name="+name+"&service=booking&comparison_rate=1229&full_stay_selected=undefined&comparison_currency=USD&api_token=I989XarlCIBkZvdj5WAWZUboOWkgneooLiTWTQC3JGOVrLre7erH8wdlfIhG")
            print(api_call.text)
            room_api = api_call.json()
            Roomsteals_ID = str(room_api["property_id"])

        for x,date in enumerate(dates):

            loop_check_in = date

            # url = "https://roomsteals.com/property-redirect?rooms=1&adults=3&children=0&checkIn="+loop_check_in+"&checkOut="+loop_check_in+"&property=579&vendor=roomsteals&nightly_rate=35.29&full_stay_rate=121.49&theme=standard"
            url = "https://roomsteals.com/property-redirect?rooms=1&adults=3&children=0&checkIn="+loop_check_in+"&checkOut="+loop_check_in+"&property="+Roomsteals_ID

            driver.get(url)
            print("going to this site",url)
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            found_room = False
            for i,room in enumerate(soup.select(".ArnRateFromTo")):
                text = room.parent.text.lower()
                for filter in Bed_Filter.split(","):
                    filter = filter.lower()
                    results = []
                    for keyword in filter.strip().split(' '):
                        results.append(keyword in room.parent.text.lower())
                    if all(results):
                        found_room = i
                        break
                if found_room:
                    break


            try:
                price = soup.select(".ArnNightlyRate")[found_room].get('total')
                ppn = float(Rooms)*float(price.split(' ')[0])*float(increase_by)
                print('found',ppn,url)
            except Exception as e:
                print(e)
                # raise("hell")

                price = 2000.00
                ppn = 2000.00
                print('not found',ppn,url)
                # continue







            db_connection = create_engine(db_connection_str)
            Clients_DF = pd.read_sql('SELECT * FROM Clients', con=db_connection)
            Client = Clients_DF[Clients_DF["Client ID"]==listing["PartnerID"]]

            # db_connection = create_engine(db_connection_str)
            # Clients_DF.to_sql("RawEmails",con=db_connection, if_exists="replace", index=False)


            if not logged_into_hosttools:
                driver.get("https://app.hosttools.com/login")
                time.sleep(5)
                driver.find_element_by_css_selector('#username').send_keys(Client["Hosttools_Username"].item())
                driver.find_element_by_css_selector('#password').send_keys(Client["Hosttools_Password"].item())
                driver.find_element_by_css_selector('#root > div > div.d-flex.container-fluid.flex-fill > div > div.col-lg-6.col-md-12.d-flex.justify-content-center > div > form > button').click()

                print("logged in")

                driver_cookies = driver.get_cookies()
                c = {c['name']:c['value'] for c in driver_cookies}
                # res = requests.get(driver.current_url,cookies=c)
                time.sleep(15) #This is the fix
                logged_into_hosttools = True


            url = "https://app.hosttools.com/setPriceOverride"

            payload = json.dumps({
            "startDate": loop_check_in+timezone,
            "endDate": loop_check_in+timezone,
            "listingID": hosttools_listingID,
            "prices": {
                "all": {
                "enabled": True,
                "price": str(ppn)
                }   
            }
            })
            headers = {
            'content-type': 'application/json',
            # 'cookie': '_gcl_au=1.1.1042685296.1626822091; _ga=GA1.2.1362656745.1626822091; _hjid=f2fec9ce-e80f-428d-9bff-1d21b74f036d; intercom-id-eagocqix=0aad9599-d51f-4dfe-8e2c-bc4bc460ec09; __stripe_mid=2c359fb2-e22e-41b7-9a4a-6fc3be58395dbf36a6; connect.sid=s%3AZwuvpGNZdEQQXf5J4ahYPlG_bFCcM-t7.I0MNSDav%2BQm9xsG6OdnKzc3OvKWb2kV8HbDh6gku3ck; _gid=GA1.2.86904523.1627521440; _hjAbsoluteSessionInProgress=0; __stripe_sid=b7756007-96f2-4b60-9963-5c3147ef73ffcdc025; _gat_UA-2445456-23=1; _hjIncludedInPageviewSample=1; _hjIncludedInSessionSample=0; intercom-session-eagocqix=THZwbURQRDkyWWQ5aDVBVG9pK2U3Z0pzQXZnRXJySW4zSXVSU3VRY2g3Q1RjeWdFaXBxWEFQcEpCYnhHUUYwNy0tUG93K296TFErSHFwdFYwdDBLSU14UT09--2f3493198e38998ef7342e3aff155fc185947f06'
            }
            try:
                response = driver.request("POST", url, headers=headers, data=payload,cookies=c)
                # responses.append({"status_code":str(response.status_code),"hosttools_listingID":hosttools_listingID,"increase_by":increase_by,"price_per_night":ppn,"check_in":loop_check_in,"date":str(datetime.datetime.now())})
                if response.status_code != 200:
                    print("error",response.status_code,response.text)
                print("Updated","status_code",str(response.status_code),"hosttools_listingID",hosttools_listingID,"increase_by",increase_by,"price_per_night",ppn,"check_in",loop_check_in) 
            except:
                print("error2",response.status_code,response.text)
                break


        url = "https://app.hosttools.com/forceUpdatePricing"
        payload = json.dumps({
        "listingID": hosttools_listingID
        })
        response = driver.request("POST", url, headers=headers, data=payload)
        print(response.status_code)
        time.sleep(5)
        driver.quit()
        db_connection = create_engine(db_connection_str)
        conn = db_connection.connect()
        result = db_connection.execute("update Config set Updated_At = '"+datetime.datetime.now().strftime("%D %H:%M")+"' where hosttools_listingID='"+hosttools_listingID+"'")
    except:
        print("next listing..")            
        driver.quit()
        db_connection = create_engine(db_connection_str)
        conn = db_connection.connect()
        result = db_connection.execute("update Config set Updated_At = 'Failed at "+datetime.datetime.now().strftime("%D %H:%M")+"' where hosttools_listingID='"+hosttools_listingID+"'")

    
    


        

            







# %%
