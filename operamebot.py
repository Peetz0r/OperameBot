#!/bin/env python3

import MySQLdb, irc.client, ssl, time, configparser

config = configparser.ConfigParser()
config.read('config.ini')
print(config.sections())

print('connecting to database... ', end='')
db = MySQLdb.connect(host=config['db']['host'], user=config['db']['user'], password=config['db']['pass'], db=config['db']['db'])
c = db.cursor()
print('done')

target = '#revspace-test'
id_order_laatste = 0

def on_connect(connection, event):
  connection.join(target)
  return

def on_join(connection, event):
  print('joined %s' % (target))
  c.execute('''
    SELECT o.id_order, o.total_paid, o.date_add, c.name
    FROM ps_orders AS o
    LEFT JOIN ps_carrier AS c          # implicit join zou geen resultaten van virtuele orders teruggeven
    ON o.id_carrier = c.id_carrier
    WHERE o.current_state = 2          # 2 is 'Betaling Aanvaard'
    ORDER BY id_order DESC
    LIMIT 1
  ''')
  r = c.fetchone()
  global id_order_laatste
  id_order_laatste = r[0]
  soort = (r[3] or 'Donatie').split()[-1]
  line = 'Laatste bestelling: #%d van €%.2f (%s) geplaatst op %s' % (r[0], r[1], soort, r[2].strftime('%Y-%m-%d %X'))
  print(line)
  connection.privmsg(target, line)
  bot.execute_every(10, checkshop, (connection,))

def on_disconnect(connection, event):
    raise SystemExit()

def checkshop(connection):
  global id_order_laatste
  c.execute('''
    SELECT o.id_order, o.total_paid, o.date_add, c.name
    FROM ps_orders AS o
    LEFT JOIN ps_carrier AS c          # implicit join zou geen resultaten van virtuele orders teruggeven
    ON o.id_carrier = c.id_carrier
    WHERE o.current_state = 2          # 2 is 'Betaling Aanvaard'
    AND o.id_order > %d
    ORDER BY id_order ASC
    LIMIT 1
  ''' % (id_order_laatste))
  r = c.fetchone()
  if(r is not None):
    id_order_laatste = r[0]
    soort = (r[3] or 'Donatie').split()[-1]
    line = 'Nieuwe bestelling: #%d van €%.2f (%s) geplaatst op %s' % (r[0], r[1], soort, r[2].strftime('%Y-%m-%d %X'))
    print(line)
    connection.privmsg(target, line)
  else:
    print('found no new orders')


ssl_factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
client = irc.client.IRC()

print('connecting to irc... ', end='')
bot = client.server().connect(config['irc']['host'], int(config['irc']['port']), config['irc']['nick'], connect_factory=ssl_factory)
print('done')

bot.add_global_handler("welcome", on_connect)
bot.add_global_handler("join", on_join)
bot.add_global_handler("disconnect", on_disconnect)

client.process_forever()
