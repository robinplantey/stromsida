#!/usr/bin/python3
# coding: utf-8

import time
from calendar import timegm
import os
import requests
import json
import numpy as np
import pandas as pd


api_root = "https://www.hvakosterstrommen.no/api/v1/prices/"
log_path = os.getcwd()+"/../var/log"

## Date/time handling

def daysAgo(n):
    return time.localtime(time.time()-n*86400)

def dateIndex(timestamp): #Inverse function of dayAgo
    return int(timestamp//86400-time.time()//86400)

def parseTime(string):
    return time.strptime(string, "%Y-%m-%dT%H:%M:%S%z")
    
def timestamp(string):
    return timegm(parseTime(string))

## Data analysis and visualization

def cheapHours(data, discount):
    hours = list(data[(1-data["NOK_per_kWh"]/data["NOK_per_kWh"].mean() > discount) | (data["NOK_per_kWh"] < 0)].sort_values("NOK_per_kWh").index)
    if len(hours) > 0:
        return True, hours
    else:
        return False, None
    
def cheapestInterval(data, length):
    if length > len(data):
        print("Data and interval length mismatch")
        return None
    else:
        p = []
        for start in range(len(data)-length+1):
            p.append(data.iloc[start:start+length].mean())
        optPrice = min(p)
        optStart = p.index(optPrice)
        return optStart, optPrice
      

## Logging

def logMsg(msg):
	t = time.strftime("%d.%m.%y %H:%M:%S", time.localtime())
	with open(log_path, "a") as logfile:
        	logfile.write("{} : {}\n".format(t, msg))



## A class to handle the prices data

class prices:
    def __init__(self, path, Ndays=None):
        self.filepath = path
        
        if os.path.exists(self.filepath):
            if Ndays is None:
                self.table = pd.read_json(self.filepath, lines=True)
            else:
                self.table = pd.read_json(self.filepath, lines=True).tail(24*Ndays)
        else:
            self.table = pd.DataFrame()

    def get(self, day, month, year, zone):
        r = requests.get(api_root+"{}/{:0>2}-{:0>2}_{}.json".format(year, month, day, zone))
        if r.status_code != 200:
            logMsg("Failed to retrieve daily prices (HTTP {})".format(r.status_code))
            return -1
        else:
            logMsg("Successfully retrieved daily prices for {:0>2}.{:0>2}.{}".format(day, month, year))
            with open(self.filepath, "a") as fp:
                for line in json.loads(r.text):
                    fp.write(str(line).replace("\'","\"")+"\n")
            self.table = pd.read_json(self.filepath, lines=True)
            return 0
    
    def update(self):
        
        status = 0
        last = dateIndex(timestamp(self.table["time_start"].iloc[-12]))
        
        for n in range(-last):
            date = daysAgo(-last-n-1)
            self.get(date.tm_mday, date.tm_mon, date.tm_year, "NO3")
            status = 1
            logMsg("Status: {}".format(status)) #DEBUG
            debugDate = parseTime(self.table["time_start"].iloc[-1]) #DEBUG
            logMsg("Last available data: {}.{}.{} ({})".format(debugDate.tm_mday, debugDate.tm_mon, debugDate.tm_year, dateIndex(timestamp(self.table["time_start"].iloc[-12])))) #DEBUG
        
        last = dateIndex(timestamp(self.table["time_start"].iloc[-12]))
        
        if last==0 and time.localtime(time.time()).tm_hour >= 13:
            date = daysAgo(-1)
            self.get(date.tm_mday, date.tm_mon, date.tm_year, "NO3")
            status = 2
            logMsg("Status: {}".format(status)) #DEBUG
            debugDate = parseTime(self.table["time_start"].iloc[-1]) #DEBUG
            logMsg("Last available data: {}.{}.{} ({})".format(debugDate.tm_mday, debugDate.tm_mon, debugDate.tm_year, dateIndex(timestamp(self.table["time_start"].iloc[-12])))) #DEBUG
        
        return status
        
    
            
    def dump(self):
        self.table.to_json(self.path)
            
    def addTimestamp(self):
        self.table["timestamp"] = self.table["time_start"].apply(timestamp)
        
    def lastData(self):
        date = time.strptime(self.table["time_start"].iloc[-1], "%Y-%m-%dT%H:%M:%S+02:00")
        return date.tm_mday, date.tm_mon, date.tm_year
    
    def SMA(self, interval):
        return pd.concat([self.table[["NOK_per_kWh","EUR_per_kWh","EXR"]].rolling(window=interval).mean(), self.table[["time_start","time_end"]]], axis=1)
    
    def hourlyPricesToday(self):
        data = self.table[self.table["time_start"].str.contains(time.strftime("%Y-%m-%d", time.localtime()))]
        return {"prices": list(np.round(data["NOK_per_kWh"], 2)) , "t": ["{:0>2}".format(x) for x in range(24)]}
    
    def averageToday(self):
        return np.round(np.mean(self.hourlyPricesToday()["prices"]),2)
    
    def dailyAverage(self, days, json=False):
        if days > len(self.table)//24:
            days = len(self.table)//24
            print("Data available only for the last {} days".format(days))
            
        df = []
        
        b = dateIndex(timestamp(self.table["time_start"].iloc[-1]))==1
        
        for i in range(b, days+b):
            data = []
            data = list(self.table[["NOK_per_kWh","EUR_per_kWh","EXR"]].iloc[::-1].iloc[i*24:(i+1)*24].mean())
            data.append(time.strftime("%d.%m.%y", parseTime(self.table["time_start"].iloc[-24*(i+1)])))
            df.append(data)
        df = pd.DataFrame(df, columns=["NOK_per_kWh","EUR_per_kWh","EXR","Date"])[::-1]

        if not json:
            return df
        else:
            price = list(df["NOK_per_kWh"])
            date = list(df["Date"])
            return {"prices": list(np.round(price, 2)), "t": date}
        
    
    def priceChange(self, interval):
        
        if interval == "1d":
            average = self.dailyAverage(2)
            prevAverage = average["NOK_per_kWh"].iloc[-2]
            nextAverage = average["NOK_per_kWh"].iloc[-1]
            delta = (nextAverage - prevAverage)/(prevAverage)
            return delta
        elif interval == "7d":
            average = self.dailyAverage(8)
            prevAverage = average["NOK_per_kWh"].iloc[-8:-1].mean()
            nextAverage = average["NOK_per_kWh"].iloc[-1].mean()
            delta = (nextAverage - prevAverage)/(prevAverage)
            return delta
        elif interval == "30d":
            average = self.dailyAverage(31)
            prevAverage = average["NOK_per_kWh"].iloc[-31:-1].mean()
            nextAverage = average["NOK_per_kWh"].iloc[-1].mean()
            delta = (nextAverage - prevAverage)/(prevAverage)
            return delta
        
        else:
            print("Invalid argument. Expected 1d, 7d or 30d")
            return None
        
    def forecast(self, json=True):
        
        t = ["{:0>2}".format(x) for x in range(24)]
        t += t
        
        h = time.localtime().tm_hour
        ind = dateIndex(timestamp(self.table["time_start"].iloc[-1]))
        
        if ind == 1:
            if json:
                return {"prices": list(np.round(self.table["NOK_per_kWh"].iloc[-48+h:], 2)), "t":t[-48+h:]}
            else:
                return self.table.iloc[-48+h:]
        elif ind == 0:
            if json:
                return {"prices": list(np.round(self.table["NOK_per_kWh"].iloc[-24+h:], 2)), "t":t[h:24]}
            else:
                return self.table.iloc[-24+h:]
        else:
            print("Neither data for today or tomorrow is available. Update before running forecast.")
            return None
        
    def cheapHours(self, discount=0.2):
        
        data = self.forecast(json=False)
        
        hours = data[(1-data["NOK_per_kWh"]/data["NOK_per_kWh"].mean() > discount) | (data["NOK_per_kWh"] < 0)].sort_values("NOK_per_kWh")
        
        if len(hours) > 0:
            
            cheapH = []
            hours["discount"] = 1-data["NOK_per_kWh"]/data["NOK_per_kWh"].mean()
            for index, row in hours.iterrows():
                date = row["time_start"]
                nextD = dateIndex(timestamp(row["time_start"])) == 1
                cheapH.append({"time":parseTime(date).tm_hour, "price":row["NOK_per_kWh"], "discount":"{:.1%}".format(row["discount"]), "nextDay": nextD})
            return True, cheapH
        else:
            return False, None

        
    ##### Convenience Methods #####
    # Return template-ready data
        
    def dashboardData(self):
        return {"avgToday": self.averageToday(),
                "lineData":{"1d": self.hourlyPricesToday(),
                            "30d": self.dailyAverage(30, True),
                            "180d": self.dailyAverage(180, True)},
                "delta":{"1d":"{:+.1%}".format(self.priceChange("1d")),
                "7d":"{:+.1%}".format(self.priceChange("7d")),
                "30d":"{:+.1%}".format(self.priceChange("30d"))}
    }
    
