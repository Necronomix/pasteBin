from flask import Flask, send_file
from flask import request
from datetime import date
import sqlite3 as sql
import unicodedata
from os import system
import os.path

app = Flask(__name__)

# The cached files are here:
CACHEPATH = "CACHE"

@app.route('/generate', methods=["POST"])
def genFile():
    """ When posted with query parameter "name", this route composes the cached json file.
    On success route returns a json object with key "filepath" which contains the path of
    the result json file. If the call fails the object contains no "filepath". Instead
    key "error" is defined.
    
    If the post contains the fields "address" and "products" (containing comma separated list
    of product ids) and the user is not
    found in the database, these fields are used to build a simplified json object."""
    if not ("name" in request.form):
        return '{"error":"No user name in request:'+str(request.form)+'"}'
    # sanitize to filename
    goodFile = sanitise_to_filename(request.form["name"])
    # Check if we have a cached file
    if os.path.isfile(CACHEPATH+"/"+goodFile):
        return '{"filepath": "'+goodFile+'"}'
   
    
    # Check if the user is in the datbase
    try:
        connection = None
        if os.path.isfile("/opt/shop.db"):
            # Running in production or testing
            connection = sql.connect("/opt/shop.db")
        else:
            connection = sql.connect("shop.db")
        cursor = connection.cursor()
        # Note that the usernames are normalized to uppercase in the database
        uppercase_name = request.form["name"].upper()
        cursor.execute("""SELECT * FROM Customers 
                            INNER JOIN Purchases ON Purchases.User=Customers.Id 
                            INNER JOIN Products ON Purchases.Product=Products.Id
                            WHERE Customers.name = %s""", uppercase_name)
        data = cursor.fetchall()
        if data != []:
            fn = build_json(data)
            return '{"filepath":"'+fn+'"}'
    except sql.Error as e:
        return '{"error":"Database error:'+str(e)+'"}'

    # We haven't found user in the database? Can we still make the json?
    if ("address" in request.form and "products" in request.form):
       datums = [(None, request.form["name"], request.form["address"], None, None, None, None, date.today(), None, pid, None, None) for pid in request.form["products"].split(",")]
       jsfile =  build_json(datums)
       return '{"filepath":"'+jsfile+'"}'
    
    # If we get here, we have failed to generate the file. Let's return an useful error message:
    return '{"error":"Invalid request:'+str(request.form)+'"}'

@app.route('/refresh',methods=["POST"])
def refresh():
    """Posting to this route with query parameter "name" should refresh the cached file.
       In practise we just delete the file and then wait for new /generate request."""
    if "name" in request.form:
        system("rm "+CACHEPATH+"/"+sanitise_to_filename(request.form["name"]))
    return "OK"

@app.route('/cache/')
def cache():
    """ This route returns the cached json files. When this program is
    deployed in the full system the nginx front for the web shop
    can serve the files directly. """
    system("mkdir "+CACHEPATH)
    requestedFile= sanitise_to_filename(request.args.get("name"))
    if os.path.isfile(CACHEPATH+"/"+requestedFile):
        return send_file(CACHEPATH+"/"+requestedFile)
    return '{"error":"No cached file"}'

def sanitise_to_filename(n): 
    normalized = unicodedata.normalize("NFKC",n)
    lowered = normalized.lower()
	sanitised = lowered.translate(str.maketrans("./ ;","-7__"))
    return sanitised

def build_json(data): 
    system("mkdir "+CACHEPATH)
    handle = None
    try:
        print(("UN",data[0][1]))
        fn = sanitise_to_filename(data[0][1])
        handle = open(CACHEPATH+"/"+fn,"w")
        handle.write('{')
        handle.write('"username": "'+data[0][1]+'"')
        print("There are "+str(len(data))+" items")
        handle.write(',"events":[')
        for (i,(_, dbname, addr1, addr2, addr3, _, _, date_of_purchase, _, item, price, _)) in enumerate(data):
            if i>0: handle.write(',')
            handle.write('{')
            handle.write('"type": "purchase"')
            handle.write(',"item": "'+item+'"')
            handle.write(',"date": "'+str(date_of_purchase)+'"')
            handle.write(',"price": "'+(str(price) or "?")+'"')
            handle.write(',"address1": "'+addr1+'"')
            handle.write(',"address2": "'+(addr2 or "?")+'"')
            handle.write(',"address3": "'+(addr3 or "?")+'"')
            handle.write('}')
        handle.write(']}')
        handle.close()
        return fn
    except Exception as e: 
        print("error")
        handle.close()
        system("rm "+fn)
        raise e

if __name__ == '__main__':
    # TODO: Remember to set debug=False before deploying!
    app.run(host="0.0.0.0",debug=True)
