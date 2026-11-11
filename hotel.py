from flask import Flask, request
from collections import defaultdict
from datetime import datetime
class Person:
    def __init__(self,name):
        self.name = name
    def info(self):
        return self.name
class Courier(Person):
    def __init__(self,name):
        super().__init__(name)
        self.delivered = []
        self.busy = False
        self.balance = 0
    def rate(self,distance):
        if distance > 0:
            return distance * 10
    def info(self):
        return f"Courier {self.name}, доставок: {len(self.delivered)}"
class BikeCourier(Courier):
    def __init__(self,name):
        super().__init__(name)
    def rate(self,distance):
        if distance > 10:
           return 'Too far'
        if distance > 0:
           return distance * 8
class CarCourier(Courier):
    def __init__(self,name):
        super().__init__(name)
    def rate(self,distance):
        if distance > 0:
            return  distance * 12 + 50
class Delivery:
    def __init__(self):
        self.couriers = {}
        self.orders = {}# {1: {'address': 'Lenina 5', 'distance': 7, 'status': 'new', 'courier': None}..}
        self.next_id = 1
        self.log = []
    def add_courier(self,name,kind):
        if name not in self.couriers and kind in ('car','bike'):
            if kind == 'car':
                self.couriers[name] = CarCourier(name)
            elif kind == 'bike':
                self.couriers[name] = BikeCourier(name)
            return 'Success'
        return 'Error'
    def create_order(self,address,distance):
        if distance > 0:
            self.orders[self.next_id] = {'address': address, 'distance': distance,'status':'new','courier' : None}
            self.next_id += 1
            return f'Order {self.next_id-1} created'
        return 'Error'
    def assign(self,order_id,courier):
        if order_id in self.orders and self.orders[order_id]['status'] == 'new' and courier in self.couriers and self.couriers[courier].busy == False:
            if self.couriers[courier].rate(self.orders[order_id]['distance']) != 'Too far':
                self.orders[order_id]['status'] = 'assigned'
                self.orders[order_id]['courier'] = courier
                self.couriers[courier].busy = True
                return 'Success'
            return 'Error'
        return 'Error'
    def complete(self,order_id):
        if  order_id in self.orders and self.orders[order_id]['status'] == 'assigned':
             self.orders[order_id]['status'] = 'done'
             courier_name = self.orders[order_id]['courier']
             self.couriers[courier_name].busy = False
             self.couriers[courier_name].delivered.append(order_id)
             price = self.couriers[courier_name].rate(self.orders[order_id]['distance'])
             self.couriers[courier_name].balance += price
             self.log.append(f"{datetime.now().strftime('%H-%M-%S')} : {courier_name} доставил {order_id}, цена {price}")
             return 'Success'
        return 'Error'
    def cancel(self,order_id):
        if order_id in self.orders and self.orders[order_id]['status'] == 'assigned':
            courier_name = self.orders[order_id]['courier']
            self.couriers[courier_name].busy = False
            self.orders[order_id]['status'] = 'cancelled'
            return 'Success'
        elif order_id in self.orders and self.orders[order_id]['status'] == 'new':
            self.orders[order_id]['status'] = 'cancelled'
            return 'Success'
        return 'Error'
    def free_couriers(self):
        arr = []
        for c in self.couriers.values():
            if c.busy == False:
                arr.append(c.info())
        if arr:
            return arr
        return 'Not found'
    def earnings(self,name):
        if name in self.couriers:
            return str(self.couriers[name].balance)
        return 'Error'
    def best_courier(self):
        d = defaultdict(int)
        for n, c in self.couriers.items():
            for x in c.delivered:
                d[n] += 1
        max_d = -1
        best_c = 'Error'
        for c, t in d.items():
            if t > max_d:
                max_d = t
                best_c = c
        if best_c == 'Error':
            return best_c
        return self.couriers[best_c].info()
    def report(self):
        arr = []
        for id, i in self.orders.items():
            arr.append(f"{id}: {i['address']} - {i['status']}")
        if arr:
            return arr
        return 'Error'
app = Flask(__name__)
mydelivery = Delivery()
@app.route('/courier')
def cour():
    s = request.args
    return mydelivery.add_courier(s['name'],s['kind'])
@app.route('/new')
def ordering():
    s = request.args
    return mydelivery.create_order(s['address'],float(s['distance']))
@app.route('/assign')
def assgn():
    s = request.args
    return mydelivery.assign(int(s['id']),s['courier'])
@app.route('/complete')
def compl():
    s = request.args
    return mydelivery.complete(int(s['id']))
@app.route('/cancel')
def canc():
    s = request.args
    return mydelivery.cancel(int(s['id']))
@app.route('/free')
def freeshow():
    output = mydelivery.free_couriers()
    if output == 'Not found':
        return output
    return '<br>'.join(output)
@app.route('/earnings')
def earn():
    s = request.args
    return mydelivery.earnings(s['name'])
@app.route('/best')
def bestw():
    return mydelivery.best_courier()
@app.route('/report')
def rep():
    output = mydelivery.report()
    if output == 'Error':
        return output
    return '<br>'.join(output)
#/courier?name=&kind=, /new?address=&distance=, /assign?id=&courier=,
# /complete?id=, /cancel?id=, /free, /earnings?name=, /best, /report

# ====================== САЙТ (frontend) ======================
# Страница открывается на главной "/" и ходит в твои же маршруты через fetch.
PAGE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FoodBooking</title>
<style>
  :root{
    --bg:#f6f4ef; --card:#ffffff; --ink:#1d1b16; --muted:#6f6a5f; --line:#e4dfd3;
    --accent:#d9480f; --accent-ink:#fff; --ok:#2b8a3e; --bad:#c92a2a; --chip:#f1ede2;
  }
  @media (prefers-color-scheme: dark){
    :root{ --bg:#16140f; --card:#211e17; --ink:#f3efe4; --muted:#a39d8d; --line:#35312664;
           --accent:#ff7a3d; --accent-ink:#1a1006; --ok:#69db7c; --bad:#ff8787; --chip:#2c281f; }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
  header{padding:22px 16px 6px;max-width:1040px;margin:0 auto}
  h1{margin:0;font-size:26px;letter-spacing:-.02em}
  h1 span{color:var(--accent)}
  .sub{color:var(--muted);font-size:14px;margin-top:2px}
  main{max-width:1040px;margin:0 auto;padding:12px 16px 80px;display:grid;gap:14px;grid-template-columns:1fr 1fr}
  @media (max-width:760px){ main{grid-template-columns:1fr} }
  .col{display:grid;gap:14px;align-content:start}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
  .card h2{margin:0 0 10px;font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
  label{display:block;font-size:13px;color:var(--muted);margin:8px 0 3px}
  input,select{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);font:inherit}
  input:focus,select:focus{outline:2px solid var(--accent);outline-offset:1px}
  .row{display:flex;gap:8px}
  .row>*{flex:1}
  button{margin-top:12px;padding:10px 14px;border:0;border-radius:10px;background:var(--accent);color:var(--accent-ink);font:inherit;font-weight:600;cursor:pointer}
  button.ghost{background:var(--chip);color:var(--ink)}
  button:hover{filter:brightness(1.06)}
  button:active{transform:translateY(1px)}
  .list{display:grid;gap:8px}
  .item{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 12px;background:var(--bg);border:1px solid var(--line);border-radius:10px;font-size:15px}
  .empty{color:var(--muted);font-size:14px;padding:6px 2px}
  .tag{font-size:12px;font-weight:700;padding:3px 9px;border-radius:99px;background:var(--chip);white-space:nowrap}
  .tag.new{color:#1c7ed6}.tag.assigned{color:#e8590c}.tag.done{color:var(--ok)}.tag.cancelled{color:var(--bad)}
  #toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(20px);opacity:0;
         padding:11px 18px;border-radius:12px;background:var(--ink);color:var(--bg);font-weight:600;
         transition:.25s;pointer-events:none;max-width:90vw;text-align:center}
  #toast.show{opacity:1;transform:translateX(-50%)}
  #toast.err{background:var(--bad);color:#fff}
  .big{font-size:22px;font-weight:700;margin-top:10px}
</style>
</head>
<body>
<header>
  <h1>Food<span>Booking</span></h1>
  <div class="sub">Служба доставки · работает на твоём Flask-бэкенде</div>
</header>

<main>
  <div class="col">
    <section class="card">
      <h2>1. Новый курьер</h2>
      <label for="cname">Имя</label>
      <input id="cname" placeholder="Aibek">
      <label for="ckind">Транспорт</label>
      <select id="ckind">
        <option value="bike">Велосипед (до 10 км)</option>
        <option value="car">Машина</option>
      </select>
      <button id="addCourier">Добавить курьера</button>
    </section>

    <section class="card">
      <h2>2. Новый заказ</h2>
      <label for="addr">Адрес</label>
      <input id="addr" placeholder="Lenina 5">
      <label for="dist">Расстояние, км</label>
      <input id="dist" type="number" min="0" step="0.5" placeholder="5">
      <button id="addOrder">Создать заказ</button>
    </section>

    <section class="card">
      <h2>3. Управление заказом</h2>
      <div class="row">
        <div><label for="oid">№ заказа</label><input id="oid" type="number" min="1" placeholder="1"></div>
        <div><label for="oc">Курьер</label><input id="oc" placeholder="Aibek"></div>
      </div>
      <div class="row">
        <button id="assign">Назначить</button>
        <button id="complete">Выполнен</button>
        <button id="cancel" class="ghost">Отмена</button>
      </div>
    </section>
  </div>

  <div class="col">
    <section class="card">
      <h2>Заказы</h2>
      <div id="orders" class="list"></div>
    </section>

    <section class="card">
      <h2>Свободные курьеры</h2>
      <div id="free" class="list"></div>
    </section>

    <section class="card">
      <h2>Заработок и лучший курьер</h2>
      <div class="row">
        <input id="ename" placeholder="Имя курьера">
        <button id="earn" style="margin-top:0">Узнать</button>
      </div>
      <div id="earnOut" class="big">—</div>
      <button id="best" class="ghost">Лучший курьер</button>
      <div id="bestOut" class="big" style="font-size:17px">—</div>
    </section>
  </div>
</main>

<div id="toast"></div>

<script>
const $ = id => document.getElementById(id);

// Вызов твоих маршрутов: /courier?name=..&kind=.. и т.д.
async function api(path, params = {}) {
  const q = new URLSearchParams(params).toString();
  const r = await fetch(path + (q ? '?' + q : ''));
  const text = await r.text();
  if (!r.ok) throw new Error('Сервер вернул ' + r.status);
  return text;
}

let tTimer;
function toast(msg, bad = false) {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'show' + (bad ? ' err' : '');
  clearTimeout(tTimer);
  tTimer = setTimeout(() => t.className = '', 2600);
}

function isErr(s) { return s === 'Error' || s === 'Not found'; }

// /free и /report отдают строки через <br> -> разбираем как текст (безопасно)
function renderList(el, text, withStatus) {
  el.replaceChildren();
  if (isErr(text) || !text.trim()) {
    const d = document.createElement('div');
    d.className = 'empty';
    d.textContent = withStatus ? 'Заказов пока нет' : 'Свободных курьеров нет';
    el.appendChild(d);
    return;
  }
  for (const line of text.split('<br>')) {
    const item = document.createElement('div');
    item.className = 'item';
    const left = document.createElement('span');
    if (withStatus) {
      const i = line.lastIndexOf(' - ');
      left.textContent = i > 0 ? line.slice(0, i) : line;
      item.appendChild(left);
      const st = i > 0 ? line.slice(i + 3) : '';
      const tag = document.createElement('span');
      tag.className = 'tag ' + st;
      tag.textContent = st;
      item.appendChild(tag);
    } else {
      left.textContent = line;
      item.appendChild(left);
    }
    el.appendChild(item);
  }
}

async function refresh() {
  try {
    renderList($('orders'), await api('/report'), true);
    renderList($('free'), await api('/free'), false);
  } catch (e) { toast(e.message, true); }
}

// Универсальная кнопка: вызвать маршрут, показать результат, обновить списки
async function act(path, params, okText) {
  try {
    const res = await api(path, params);
    const bad = isErr(res);
    toast(bad ? 'Ошибка: проверь данные' : (okText || res), bad);
    await refresh();
    return res;
  } catch (e) { toast(e.message, true); }
}

$('addCourier').onclick = async () => {
  const name = $('cname').value.trim();
  if (!name) return toast('Введи имя', true);
  const r = await act('/courier', { name, kind: $('ckind').value }, 'Курьер ' + name + ' добавлен');
  if (r === 'Success') { $('oc').value = $('oc').value || name; $('ename').value = $('ename').value || name; $('cname').value = ''; }
};

$('addOrder').onclick = async () => {
  const address = $('addr').value.trim(), distance = $('dist').value;
  if (!address || !distance) return toast('Заполни адрес и расстояние', true);
  const r = await act('/new', { address, distance });
  if (r && r.startsWith('Order')) { $('oid').value = r.split(' ')[1]; $('addr').value = ''; $('dist').value = ''; }
};

const needId = () => { if (!$('oid').value) { toast('Введи № заказа', true); return false; } return true; };

$('assign').onclick = () => {
  if (!needId()) return;
  if (!$('oc').value.trim()) return toast('Введи имя курьера', true);
  act('/assign', { id: $('oid').value, courier: $('oc').value.trim() }, 'Заказ назначен');
};
$('complete').onclick = () => { if (needId()) act('/complete', { id: $('oid').value }, 'Заказ выполнен'); };
$('cancel').onclick   = () => { if (needId()) act('/cancel',   { id: $('oid').value }, 'Заказ отменён'); };

$('earn').onclick = async () => {
  const name = $('ename').value.trim();
  if (!name) return toast('Введи имя', true);
  try {
    const r = await api('/earnings', { name });
    $('earnOut').textContent = isErr(r) ? 'Курьер не найден' : r + ' сом';
  } catch (e) { toast(e.message, true); }
};
$('best').onclick = async () => {
  try {
    const r = await api('/best');
    $('bestOut').textContent = isErr(r) ? 'Пока нет доставок' : r;
  } catch (e) { toast(e.message, true); }
};

refresh();
</script>
</body>
</html>
"""


@app.route('/')
def home():
    return PAGE
