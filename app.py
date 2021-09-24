import flask
from flask.templating import render_template
import pymongo
from riotwatcher import LolWatcher, ApiError
from werkzeug.utils import redirect
import datetime
import hashlib
import os
import string
import random
from dotenv import load_dotenv

load_dotenv()
watcher = LolWatcher(os.getenv('RIOT_API'))

app = flask.Flask(__name__)

myclient = pymongo.MongoClient(os.getenv("MONGODB"))
mydb = myclient["accountManager"]
accountColl = mydb["account"]
userColl = mydb["user"]
app.secret_key = os.getenv("SECRET_KEY")

app.config["CORS_HEADERS"] = 'Content-Type'

class Account:
    name = ""
    loginName = ""
    region = ""
    elo = ""
    lastPlayed = ""
    notes = ""
    opggRegion = ""
    regionName = ""
    lp = ""
    eloColor = ""
    datetimeColor = ""

    def __init__(self, name, region, elo, lastPlayed, notes, lp, loginName):
        self.name = name
        self.region = region
        self.elo = elo
        self.lastPlayed = lastPlayed
        self.notes = notes
        self.lp = lp
        self.loginName = loginName
        self.eloColor = getEloColor(elo)

        diff = (datetime.datetime.now() - lastPlayed).days

        if(diff < 7):
            self.datetimeColor = "#549291"
        elif(diff < 30):
            self.datetimeColor = "#cc8d36"
        else:
         self.datetimeColor = "#e51e24"

        if(region == "EUW1"):
            self.opggRegion = "euw."
            self.regionName = "EUW"
        elif(region == "EUN1"):
            self.opggRegion = "eune."
            self.regionName = "EUNE"
        elif(region == "KR"):
            self.opggRegion = ""
            self.regionName = "Korea"
        elif(region == "JP1"):
            self.opggRegion = "jp."
            self.regionName = "Japan"
        elif(region == "NA1"):
            self.opggRegion = "na."
            self.regionName = "NA"
        elif(region == "OC1"):
            self.opggRegion = "oce."
            self.regionName = "Oceania"
        elif(region == "BR1"):
            self.opggRegion = "br."
            self.regionName = "Brazil"
        elif(region == "LA2"):
            self.opggRegion = "las."
            self.regionName = "LAN-South"
        elif(region == "LA1"):
            self.opggRegion = "lan."
            self.regionName = "LAN-North"
        elif(region == "RU"):
            self.opggRegion = "ru."
            self.regionName = "Russia"
        elif(region == "TR1"):
            self.opggRegion = "tr."
            self.regionName = "Turkey"


@app.route('/')
@app.route('/index')
def handleIndex():
    user = authenticate()
    if(user == False):
        return redirect('/login')

    accounts = []

    for f in accountColl.find({'user': user['name']}):
        accounts.append(getUser(f['name'], f['region'], f['elo'], f['lastPlayed'], f['notes'], f['lp'], f['loginName']))

    accounts = sorted(accounts, key=lambda account: (account.region, getEloNumber(account.elo)))

    return flask.render_template('index.html', accounts=accounts)

@app.route('/addAccount')
def addAccount():
    return flask.render_template("addAccount.html")

@app.route('/pAddAccount', methods=["POST"])
def postAddAccount():
    user = authenticate()
    if(user == False):
        return redirect('/login')



    name = flask.request.form['name']
    loginName = flask.request.form['loginName']
    region = flask.request.form['region']
    notes = flask.request.form['notes']
    
    if(accountColl.find_one({"name": name}) != None):
        return redirect("/index")

    mydict = getDict(name, region, notes, loginName, user['name'])
    
    accountColl.insert_one(mydict)

    return redirect("/index")

@app.route('/refresh')
def refreshData():
    for f in accountColl.find():
        mydict = getDict(f['name'], f['region'], f['notes'], f['loginName'])
        accountColl.update_one({'name': mydict['name']}, {"$set": {"name": mydict['name'], "region": mydict['region'], "notes": mydict['notes'], "elo": mydict['elo'], "lastPlayed": mydict['lastPlayed'], 'lp': mydict['lp'], 'loginName': mydict['loginName']}})

    return redirect("/index")

@app.route('/remove/<path:accountName>')
def remove(accountName):
    user = authenticate()
    if(user == False):
        return redirect('/login')

    accountColl.delete_one({"name": accountName, "user": user})
    
    return redirect("/index")

@app.route('/edit/<path:accountName>')
def edit(accountName):
    mydict = accountColl.find_one({'name': accountName})

    print(mydict['region'])

    return flask.render_template('editAccount.html', accountName=accountName, notes=mydict['notes'], region=mydict['region'], loginName=mydict['loginName'])

@app.route('/pEdit/<path:accountName>', methods=["POST"])
def postEdit(accountName):
    user = authenticate()
    if(user == False):
        return redirect('/login')

    name = flask.request.form['name']
    region = flask.request.form['region']
    notes = flask.request.form['notes']
    loginName = flask.request.form['loginName']
    
    mydict = getDict(name, region, notes, loginName, user['name'])

    accountColl.update_one({'name': accountName, 'user': user['name']}, {"$set": {"name": mydict['name'], "region": mydict['region'], "notes": mydict['notes'], "elo": mydict['elo'], "lastPlayed": mydict['lastPlayed'], 'lp': mydict['lp'], 'loginName': mydict['loginName']}})

    return redirect("/index")

@app.route('/login')
def login():
    return render_template("login.html")
    
@app.route('/register')
def register():
    return render_template("register.html")

@app.route('/pLogin', methods=["POST"])
def pLogin():
    name = flask.request.form['name']
    password = flask.request.form['password']

    acc = userColl.find_one({'name': name})

    print(acc)

    salt = acc['salt']
    key = acc['key']

    print(salt)

    new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000, dklen=128)

    print(flask.session.get('sessionID'))

    if(new_key == key):
        new_session = randomSID()
        userColl.update_one({'name': name}, {"$set": {"session": new_session}})

        flask.session['sessionID'] = new_session

        print("Correct passwort")
    else:
        print("Wrong password")

    return redirect('/index')


@app.route('/pRegister', methods=["POST"])
def pRegister():
    name = flask.request.form['name']
    password = flask.request.form['password']

    user = userColl.find_one({'name': name})

    if(user != None):
        return redirect("/register")

    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000, dklen=128)

    session = randomSID()

    mydict = {'name': name, 'salt': salt, 'key': key, 'session': session}

    userColl.insert_one(mydict)

    #login below

    flask.session['sessionID'] = session

    return redirect("/index")



def authenticate():
    sessionid = flask.session.get('sessionID')
    if(sessionid == None):
        return False

    user = userColl.find_one({'session': sessionid})

    if(user == None):
        return False

    return user

def getDict(name, region, notes, loginName, username):
    summoner = watcher.summoner.by_name(region, name)
    elo = watcher.league.by_summoner(region, summoner['id'])

    userElo = 'Unranked'
    userLP = '0'

    for e in elo:
        if(e['queueType'] == 'RANKED_SOLO_5x5'):
            userElo = e['tier'] + ' ' + e['rank']
            userLP = str(e['leaguePoints'])

    v5Region = getRegion(region)

    matches = watcher.match_v5.matchlist_by_puuid(v5Region, summoner['puuid'])
    lastMatch = watcher.match_v5.by_id(v5Region, matches[0])
    lastPlayed = datetime.datetime.fromtimestamp(lastMatch['info']['gameCreation'] / 1000)

    mydict = {"name": name, "region": region, "elo": userElo, 'lastPlayed': lastPlayed, 'notes': notes, 'lp': userLP, 'loginName': loginName, 'user': username}

    return mydict

def getUser(name, region, elo, lastPlayed, notes, lp, loginName):
    return Account(name, region, elo, lastPlayed, notes, lp, loginName)

def getRegion(region):
    if(region == 'BR1' or region == 'LA1' or region == 'LA2' or region == 'NA1' or region == 'OC1'):
        return "AMERICAS"
    if(region == 'JP1' or region == 'KR'):
        return "ASIA"
    if(region == 'EUN1' or region == 'EUW1' or region == 'RU' or region == 'TR1'):
        return "EUROPE"
	
def getEloNumber(fullElo):
    if(fullElo == 'UNRANKED'):
        return -1

    splitted = fullElo.split(' ')
    
    division = 1
    elo = splitted[0]

    if(len(splitted) == 2):
        if(splitted[1] == "IV"):
            division = 1
        elif(splitted[1] == "III"):
            division = 2
        elif(splitted[1] == "II"):
            division = 3
        elif(splitted[1] == "I"):
            division = 4

    if(elo == 'IRON'):
        return division
    if(elo == 'BRONZE'):
        return 4 + division
    if(elo == 'SILVER'):
        return 8 + division
    if(elo == 'GOLD'):
        return 12 + division
    if(elo == 'PLATINUM'):
        return 16 + division
    if(elo == 'DIAMOND'):
        return 20 + division
    if(elo == 'MASTER'):
        return 24 + division
    if(elo == 'GRANDMASTER'):
        return 28 + division
    if(elo == 'CHALLENGER'):
        return 32 + division
    return -1

def getEloColor(fullElo):
    splitted = fullElo.split(' ')
    elo = splitted[0]

    if(elo == 'UNRANKED'):
        return '#5e5757'
    if(elo == 'IRON'):
        return '#5e5757'
    if(elo == 'BRONZE'):
        return '#7f4028'
    if(elo == 'SILVER'):
        return '#849da6'
    if(elo == 'GOLD'):
        return '#cc8d36'
    if(elo == 'PLATINUM'):
        return '#549291'
    if(elo == 'DIAMOND'):
        return '#4e6a9f'
    if(elo == 'MASTER'):
        return '#8052a3'
    if(elo == 'GRANDMASTER'):
        return '#e51e24'
    if(elo == 'CHALLENGER'):
        return '#d9864d'

def randomSID():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=256))


if __name__ == '__main__':
    port=os.environ.get("PORT")
    app.run(port=(5000 if port == None else port))