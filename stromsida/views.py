import os, sys

from configparser import ConfigParser

config = ConfigParser()
config.read('.env')

path = os.path.abspath(os.getcwd()+"/backend")
sys.path.append(path)


from stroempris import *
from time import sleep
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.cache import cache_page
from django.core.cache import cache

def home(request):
    
    p = cache.get_or_set("priceObject", prices(os.getcwd()+"/../data/priser.json", 181))
    
    status = p.update()
    
    if status > 0:
        cache.clear()
    
    today = time.strftime("%a %d %b %Y", time.localtime()) 
    
    data = cache.get_or_set("dashboardData" , p.dashboardData())
    
    forecast = p.forecast()
    futureAvg = np.round(np.mean(forecast["prices"]), 2)
    
    cheapH = p.cheapHours()
    
    deltas = data["delta"]
    
    color1d = "green" if deltas["1d"][0]=="-" else "red"
    color7d = "green" if deltas["7d"][0]=="-" else "red"
    color30d = "green" if deltas["30d"][0]=="-" else "red"
    
    charts = data["lineData"]
    
    # Page from the theme 
    return render(request, "pages/dashboard.html", context={"dateToday":today , "avgToday":data["avgToday"], "cheapHours":cheapH,
                                                            "delta1d":deltas["1d"], "delta7d":deltas["7d"], "delta30d":deltas["30d"], 
                                                            "color1d":color1d, "color7d":color7d, "color30d":color30d, 
                                                            "futureData":forecast, "futureAvg":futureAvg,
                                                            "1dayData":charts["1d"], "30dayData":charts["30d"], "180dayData":charts["180d"]}) 
