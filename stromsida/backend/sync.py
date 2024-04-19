#!/usr/bin/python3
# coding: utf-8

from stroempris import *

def sync():
    
    maxRetry = 8
    
    p = prices("priser.json")
    
    status = p.update()
    
    if status:
        p.dump()
    
    while True:
        try:
            
            k = 0
    
            h = time.localtime().tm_hour
            d = time.localtime().tm_mday
            m = time.localtime().tm_mon
            y = time.localtime().tm_year
            
            if h >= 13:
                t0 = time.time()
                status = p.get(d+1, m, y, "NO3")

                while status == -1 and k < maxRetry: 

                    time.sleep(60*2**(k+1))
                    status = p.get(d+1, m, y, "NO3")
                    k += 1

                if k == maxRetry:
                    logMsg("Max number of retries exceeded. Giving up")

                time.sleep(86400 - (time.time()-t0))

        except KeyboardInterrupt:
            break
    return 0

sync()
