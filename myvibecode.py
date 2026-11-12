# My Python OOP exam preparation
from flask import Flask,request
from collections import defaultdict
from datetime import datetime
class Person:
    def __init__(self,name):
        self.name = name
    def info(self):
        return self.name
class Driver(Person):
    def __init__(self,name):
        super().__init__(name)
        self.rides = []
        self.busy = False
    def price(self,km):
        return km * 15
    def info(self):
        return f"Driver {self.name}, поездок: {len(self.rides)}"
class EconomyDriver(Driver):
    def __init__(self,name):
        super().__init__(name)
    def price(self,km):
        if km > 20:
            return 'Too far'
        return km * 12
class ComfortDriver(Driver):
    def __init__(self,name):
        super().__init__(name)
    def price(self,km):
        return km * 20 + 100
class Taxi:
    def __init__(self):
        self.drivers = {}
        self.rides = {}#1: {'start': 'Lenina 5', 'end': 'Airport', 'km': 7, 'status': 'new', 'driver': None, 'price': 0}
        self.next_id = 1
        self.log = []
    def add_driver(self,name,kind):
        if name not in self.drivers and kind in ('economy','comfort'):
            if kind == 'economy':
                self.drivers[name] = EconomyDriver(name)
            elif kind == 'comfort':
                self.drivers[name] = ComfortDriver(name)
            return 'Success'
        return 'Error'
    def order_ride(self,start,end,km):
        if km <= 0:
            return 'Error'
        self.rides[self.next_id] = {'start': start, 'end': end, 'km': km, 'status': 'new', 'driver': None, 'price': 0}
        self.next_id += 1
        return f'Ride {self.next_id-1} ordered'
    def assign(self,ride_id, driver):
        if ride_id in self.rides and driver in self.drivers and self.drivers[driver].busy == False and self.drivers[driver].price(self.rides[ride_id]['km']) != 'Too far' and self.rides[ride_id]['status'] == 'new' and self.rides[ride_id]['driver'] == None:
            self.drivers[driver].busy = True
            self.rides[ride_id]['status'] = 'assigned'
            self.rides[ride_id]['driver'] = driver
            return 'Success'
        return 'Error'
    def finish(self,ride_id):
        if  ride_id in self.rides and self.rides[ride_id]['status'] == 'assigned':
            self.rides[ride_id]['status'] = 'done'
            price = self.drivers[self.rides[ride_id]['driver']].price(self.rides[ride_id]['km'])
            self.rides[ride_id]['price'] = price
            self.drivers[self.rides[ride_id]['driver']].busy = False
            self.drivers[self.rides[ride_id]['driver']].rides.append(ride_id)
            self.log.append(f"{datetime.now().strftime('%H-%M-%S')} : {self.rides[ride_id]['driver']} довёз {ride_id}, цена {price}")
            return 'Success'
        return 'Error'
    def cancel(self,ride_id):
        if ride_id in self.rides and self.rides[ride_id]['status'] == 'assigned':
           self.rides[ride_id]['status'] = 'cancelled'
           self.drivers[self.rides[ride_id]['driver']].busy = False
           return 'Success'
        elif ride_id in self.rides and self.rides[ride_id]['status'] == 'new':
           self.rides[ride_id]['status'] = 'cancelled'
           return 'Success'
        return 'Error'
    def free_drivers(self):
        arr = []
        for n, d in self.drivers.items():
            if d.busy == False:
                arr.append(d.info())
        if arr:
            return arr
        return 'Not found'
    def earnings(self,name):
        total = 0
        for id, r in self.rides.items():
            if r['driver'] == name:
                total += r['price']
        return str(total)
    def best_driver(self):
        d = defaultdict(int)
        for r in self.rides.values():
            if r['status'] == 'done':
                d[r['driver']] += 1
        best_d = 'Error'
        most_r = -1
        for name, r in d.items():
            if r > most_r:
                most_r = r
                best_d = name
        if best_d == 'Error':
            return 'Error'
        return self.drivers[best_d].info()
    def report(self):
        arr = []
        for id, r in self.rides.items():
            arr.append(f"{id}: {r['start']} -> {r['end']} - {r['status']}")
        if arr:
            return arr
        return 'Error'
app = Flask(__name__)
mytaxi = Taxi()
@app.route('/driver')
def dr():
    s = request.args
    return mytaxi.add_driver(s['name'],s['kind'])
@app.route('/order')
def ord():
    s = request.args
    return mytaxi.order_ride(s['start'], s['end'],float(s['km']))
@app.route('/assign')
def asss():
    s = request.args
    return mytaxi.assign(int(s['id']),s['driver'])
@app.route('/finish')
def fin():
    s = request.args
    return mytaxi.finish(int(s['id']))
@app.route('/cancel')
def canc():
    s = request.args
    return mytaxi.cancel(int(s['id']))
@app.route('/free')
def ffree():
    output = mytaxi.free_drivers()
    if output == 'Not found':
        return output
    return '<br>'.join(output)
@app.route('/earnings') 
def earn():
    s = request.args
    output =  mytaxi.earnings(s['name'])
    if output == '0':
        return 'Error'
    return output
@app.route('/best')
def bst():
    return mytaxi.best_driver()
@app.route('/report')
def rep():
    output = mytaxi.report()
    if output == 'Error':
        return output
    return '<br>'.join(output)
# /free	free_drivers 
# /earnings?name=	earnings
# /best	best_driver
# /report	report (
# 