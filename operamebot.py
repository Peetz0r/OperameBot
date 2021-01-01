#!/bin/env -S python3 -u

import MySQLdb, irc.client, ssl, configparser, datetime

config = configparser.ConfigParser()
config.read('config.ini')
print(config.sections())

print('connecting to database... ', end='')
db = MySQLdb.connect(host=config['db']['host'], user=config['db']['user'], password=config['db']['pass'], db=config['db']['db'])
db.autocommit(True)
c = db.cursor()
print('done')

target = config['irc']['channel']
date_upd_laatste = datetime.datetime(1, 1, 1)

def on_connect(connection, event):
  print('connected')
  print('joining %s... ' % (config['irc']['channel']), end='')
  connection.join(target)
  return

def on_join(connection, event):
  print('joined')
  c.execute(f'''
    SELECT o.id_order, o.total_paid, o.date_add, o.date_upd, c.name
    FROM {config['db']['prefix']}orders AS o
    LEFT JOIN {config['db']['prefix']}carrier AS c          # implicit join zou geen resultaten van virtuele orders teruggeven
    ON o.id_carrier = c.id_carrier
    WHERE o.current_state = 2                               # 2 is 'Betaling Aanvaard'
    ORDER BY o.date_upd DESC
    LIMIT 1
  ''')
  r = c.fetchone()
  global date_upd_laatste
  date_upd_laatste = r[3]
  soort = (r[4] or 'Donatie').split()[-1]
  line = f"Laatste bestelling: #{r[0]} van €{r[1]:.2f} ({soort}) geplaatst op {r[2].strftime('%Y-%m-%d %X')}"
  print(line)
  connection.privmsg(target, line)
  bot.execute_every(10, checkshop, (connection,))

def on_disconnect(connection, event):
    raise SystemExit()

def checkshop(connection):
  global date_upd_laatste
  c.execute(f'''
    SELECT o.id_order, o.total_paid, o.date_add, o.date_upd, c.name
    FROM {config['db']['prefix']}orders AS o
    LEFT JOIN {config['db']['prefix']}carrier AS c          # implicit join zou geen resultaten van virtuele orders teruggeven
    ON o.id_carrier = c.id_carrier
    WHERE o.current_state = 2                               # 2 is 'Betaling Aanvaard'
    AND o.date_upd > {date_upd_laatste}
    ORDER BY o.date_upd ASC
    LIMIT 1
  ''')
  r = c.fetchone()
  if(r is not None):
    date_upd_laatste = r[3]
    soort = (r[4] or 'Donatie').split()[-1]
    line = f"Nieuwe bestelling: #{r[0]} van €{r[1]:.2f} ({soort}) geplaatst op {r[2].strftime('%Y-%m-%d %X')}"
    print()
    print(line)
    connection.privmsg(target, line)
  else:
    print('.',end='')


ssl_factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
client = irc.client.IRC()

print('connecting to %s... ' % (config['irc']['host']), end='')
bot = client.server().connect(config['irc']['host'], int(config['irc']['port']), config['irc']['nick'], connect_factory=ssl_factory)

bot.add_global_handler("welcome", on_connect)
bot.add_global_handler("join", on_join)
bot.add_global_handler("disconnect", on_disconnect)

client.process_forever()
