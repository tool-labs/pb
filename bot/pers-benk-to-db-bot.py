#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
	Wikipedia-pybot-framework is needed!
	author: [[:de:User:Euku]]
"""
import sys              # To not have wikipedia and this in one dir we'll import sys
import re               # Used for regular expressions
import os               # used for os.getcwd()
import wikipedia        # Wikipedia-pybot-framework
#import httplib
import pagegenerators
import locale			# German
from time import localtime, strftime, mktime    # strftime-Function and related
import time
import oursql

ENV = "production" # for now there is no difference
if ENV == "trunc":
	sys.path.append('/home/euku/wppb/code/p_wppb/trunk/pyapi') # TODO make this a relative path
	sys.path.append('/home/euku/wppb/code/p_wppb/trunk/web/dynamic') # TODO make this a relative path
elif ENV == "production":
	sys.path.append('/home/euku/wppb/code/p_wppb/branches/production/pyapi') # TODO make this a relative path
	sys.path.append('/home/euku/wppb/code/p_wppb/branches/production/web/dynamic') # TODO make this a relative path
import wppb
import pb_db_config

# templates and WP paths
tmplNewUser = u"Wikipedia:Persönliche Bekanntschaften/neuer Benutzer"
newUserRegex = u"\{\{" + tmplNewUser + u"\|Name=(?P<user>[^|]+)(?:\|Kommentar=.*)?\|Zeit=(?P<timemin>(?:[01]\d|2[0-3]))\:(?P<timeh>[0-5]\d)\,\ (?P<timed>[123]?\d)\.\ (?P<timemon>Jan\.|Feb\.|Mär\.|Apr\.|Mai|Jun\.|Jul\.|Aug\.|Sep\.|Okt\.|Nov\.|Dez\.)\ (?P<timeyear>2\d\d\d)\ \(CES?T\)\}\}"
newUserReplRegex = u"\{\{" + tmplNewUser + u"\|Name=%s(?:\|Kommentar=.*?)?\|Zeit=.+?\ 2\d\d\d\ \(CES?T\)\}\}[\n\r]*"
tmplNewACK = u"Wikipedia:Persönliche Bekanntschaften/neue Bestätigung"
newACKRegex = u"\{\{" + tmplNewACK + u"\|Bestätiger=(?P<certifier>[^|]+)\|Bestätigter=(?P<certified>[^|]+)\|Kommentar=(?P<comment>.*?)\|Zeit=(?P<timemin>(?:[01]\d|2[0-3]))\:(?P<timeh>[0-5]\d)\,\ (?P<timed>[123]?\d)\.\ (?P<timemon>Jan\.|Feb\.|Mär\.|Apr\.|Mai|Jun\.|Jul\.|Aug\.|Sep\.|Okt\.|Nov\.|Dez\.)\ (?P<timeyear>2\d\d\d)\ \(CES?T\)\}\}"
newACKReplRegex = u"\{\{" + tmplNewACK + u"\|Bestätiger=%s\|Bestätigter=%s\|Kommentar=.*?\|Zeit=.+?\ 2\d\d\d\ \(CES?T\)\}\}[\n\r]*"

workList = u"Wikipedia:Persönliche Bekanntschaften/neue Einträge"
userRAWListPage = u"Wikipedia:Persönliche Bekanntschaften/JS-alle Benutzer"
userListPage = u"Wikipedia:Persönliche Bekanntschaften/Teilnehmerliste"
newUserListPage = u"Wikipedia:Persönliche Bekanntschaften/Neu dazugekommen"
localLogFile = os.getcwd() + strftime("/logs/pb-bot-%Y-%m-%d.log",localtime())

# debugging
DONOTSAVEDB = False # if True => no changes will be made to the database
DONOTSAVE = False # if True => no changes will be made on Wikipedia

monthDic = {}
monthDic[u"Jan."] = 1
monthDic[u"Feb."] = 2
monthDic[u"Mär."] = 3
monthDic[u"Apr."] = 4
monthDic[u"Mai"]  = 5
monthDic[u"Jun."] = 6
monthDic[u"Jul."] = 7
monthDic[u"Aug."] = 8
monthDic[u"Sep."] = 9
monthDic[u"Okt."] = 10
monthDic[u"Nov."] = 11
monthDic[u"Dez."] = 12

def isIn(text, regex):
	return re.search(regex, text, re.UNICODE)
	
def search(text, regex):
	m = re.search(regex, text, re.UNICODE)
	if m:
	  return m.groups()[0]
	else:
	  return u""

def output(text):
	fd = open(localLogFile, 'a')
	writeMe = text + u"\n" 
	writeMe = writeMe.encode('utf-8')
	fd.write(writeMe)
	fd.close()
	wikipedia.output(text)


def writeUserListToWikipedia(db, editSummary):
	if (editSummary != u""):
		editSummary = u"Aktualisiere Benutzerliste: neue(r) Benutzer: " + editSummary
	else:
		editSummary = u"Aktualisiere Benutzerliste"
	
	# laad list
	userList = db.get_user_list_with_confirmations()
	#############################################
	# prepare the raw user list for JavaScripts #
	#############################################
	# convert it to a string
	newRawText = u""
	for u, confirmationCount, part_since_timestamp in userList:
		# former and bannen users are already left out
		newRawText += u + u"\n"
	# save RAW-list
	page = wikipedia.Page(wikipedia.getSite(), userRAWListPage)
	rawText = page.get()
	output(u"newRawText fertig")
	if newRawText != rawText + u"\n":
		output(u"RAW-Benutzerliste:")
		wikipedia.showDiff(rawText, newRawText)
	 	if not DONOTSAVE:
			page.put(newRawText, editSummary, False, minorEdit=True, force=True, maxTries=2)

	#####################################
	# prepare user list for main page   #
	#####################################
	toc = u'<noinclude>{{/Intro}}</noinclude>__NOEDITSECTION__ __NOTOC__ __NOINDEX__\n\
== Teilnehmer ==\n\
Hier geht es zu den einzelnen Unterlisten der derzeitigen \'\'\'' + str(len(userList)) + u'\'\'\' Teilnehmer:\n\
{|border="0" style="border:1px solid #aaaaaa;background-color:#f9f9f9;padding:5px;font-size: 95%;" align=center\n\
|[[#0–9|0–9]] [[#A|A]] [[#B|B]] [[#C|C]] [[#D|D]] [[#E|E]] [[#F|F]] [[#G|G]] [[#H|H]] [[#I|I]] [[#J|J]] [[#K|K]] [[#L|L]] [[#M|M]] [[#N|N]] [[#O|O]] [[#P|P]] [[#Q|Q]] [[#R|R]] [[#S|S]] [[#T|T]] [[#U|U]] [[#V|V]] [[#W|W]] [[#X|X]] [[#Y|Y]] [[#Z|Z]]\n\
|}\n'
	userTemplate = u'{{/DB-Link|%s|%s}}'
	classTemplate1 = u'===%s===\n'
	classTemplate2 = u'\n'
	separator = u"· "

	currentLetter = u"0–9"
	newRawText = toc + (classTemplate1 % currentLetter)
	for u, confirmationCount, part_since_timestamp in userList:
		if ((currentLetter == u"0–9") and (u[0] == u"A")):
			currentLetter = u"A"
			newRawText += classTemplate2 + (classTemplate1 % currentLetter)
		elif (currentLetter != u"0–9" and u[0] > currentLetter and u[0] <= u"Z"):
			currentLetter = u[0]
			newRawText += classTemplate2 + (classTemplate1 % currentLetter)
		elif userList[0] != u:
			newRawText += separator
		
		if confirmationCount < 3:
			status = u"unbestätigt"
		else:
			status = u""
		newRawText += userTemplate % (u, status)
	newRawText += classTemplate2
	output(u"newRawText 2 fertig")
	# save it
	page = wikipedia.Page(wikipedia.getSite(), userListPage)
	rawText = page.get()
	if newRawText != rawText + u"\n":
	   output(u"Teilnehmerliste:")
	   wikipedia.showDiff(rawText, newRawText)
	   if not DONOTSAVE:
		  page.put(newRawText, editSummary, False, minorEdit=True, force=True, botflag=False, maxTries=2)
	
	######################
	# write new users    #
	######################
	# prepare new-user list for main page
	newUserList = db.get_latest_user_list_with_confirmations() 
	toc = u'<noinclude>{{/Intro}}</noinclude>\n== Neu dazugekommen ==\n'
	userTemplate = u'{{/Benutzer-Link|%s|%s|%s}} '
	separator = u"· "

	newRawText = toc
	for u, confirmationCount, cfDate in newUserList:
		try:
			if confirmationCount < 3:
				userStatus = u"unbestätigt"
			else:
				userStatus = u""
			date = u"%s.%s" % (cfDate.day, cfDate.month) # convert to DD.MM.
			newRawText += userTemplate % (u, date, userStatus)
		except KeyError:
			output(u + " not found in dictionary")
	
	# save it
	page = wikipedia.Page(wikipedia.getSite(), newUserListPage)
	rawText = page.get()
	if newRawText != rawText + u" ":
	   output(u"Teilnehmerliste:")
	   wikipedia.showDiff(rawText + u" ", newRawText)
	   if not DONOTSAVE:
		  page.put(newRawText, editSummary, False, minorEdit=True, force=True, botflag=False, maxTries=2)

	output(newRawText)
	

"""
   extrats from a text all information needed: new users and new acknoledgements
   and returns it back as a tuple
"""
def divideIntoTasks(pageText):
		### find new user requests
		p = re.compile(newUserRegex, re.UNICODE)
		taskIterator = p.finditer(pageText)
		newUsers = []
		for task in taskIterator:
			if monthDic.has_key(task.group('timemon')):
			   newUsers.append((task.group('user'), int(task.group('timemin')), int(task.group('timeh')), int(task.group('timed')), monthDic[task.group('timemon')], int(task.group('timeyear'))))
		
		## find new acknowledgements
		p = re.compile(newACKRegex, re.UNICODE)
		taskIterator = p.finditer(pageText)
		newACKs = []
		for task in taskIterator:
			if monthDic.has_key(task.group('timemon')):
			   newACKs.append((task.group('certifier'), task.group('certified'), task.group('comment'), int(task.group('timemin')), int(task.group('timeh')), int(task.group('timed')), monthDic[task.group('timemon')], int(task.group('timeyear'))))
		
		return newUsers, newACKs


"""
   sends information to the DB API skript
"""
def addConfirmation(db, data):
	bestaetigerName, bestaetigterName, comment, hour, minutes, day, month, year = data

	#print data
	bestaetigerID  = db.get_user_by_name(bestaetigerName)[1]
	bestaetigterID = db.get_user_by_name(bestaetigterName)[1]
	bestaetigerCfCount = db.get_cf_count_by_confirmed(bestaetigerID)
	if (bestaetigerCfCount < 3):
		return # user is not allowed

	###### write to DB
	output(u"send it to DB API...")
	timestamp = "%s-%02d-%02d %02d:%02d:00" % (year, month, day, hour, minutes)
	#print "db.get_user_by_name(bestaetigerName)[1]", bestaetigerID
	#print "db.get_user_by_name(bestaetigterName)[1]", bestaetigterID
	if not DONOTSAVEDB:
		try:
			db.add_confirmation(bestaetigerID, bestaetigterID, comment, timestamp)
		except oursql.IntegrityError:
			# already in ... TODO change the edit comment
			output(u"confirmation %s -> %s already in" % (bestaetigerID, bestaetigterID))
	
	### check if 'bestaetigterName' is allowed to write ACKs now and leave a message on his/her talk page
	if db.get_cf_count_by_confirmed(bestaetigterID) == 3:
		# ok, write a message
		msgText = u"{{subst:Wikipedia:Persönliche Bekanntschaften/Botvorlage:Info zur dritten Bestätigung|Dritter=" + bestaetigerName + u"}}"
#		msgText = u"\n==[[Wikipedia:Persönliche Bekanntschaften]] ==\nHallo " + bestaetigterName + u".\nDu wurdest vor ein paar Minuten von " + bestaetigerName + u" bestätigt und hast damit insgesamt drei Bestätigungen. D.h. von nun an darfst du [[Wikipedia:Persönliche Bekanntschaften/neue Anfragen|selber Bestätigungen verteilen]] an Wikipedianer, die du persönlich kennengelernt hast. Bei Fragen wende dich [[Wikipedia Diskussion:Persönliche Bekanntschaften|hier]] hin. Gruß --~~~~"
		output(u"war unbestaetigt und darf nun selber bestaetigen")
		UserTalkPage = wikipedia.Page(wikipedia.getSite(), u"Benutzer_Diskussion:" + bestaetigterName)
		if DONOTSAVE: return
		try:
			UserTalkPage.put(UserTalkPage.get() + msgText, u"du wurdest zum dritten Mal bestätigt", False, minorEdit=False, force=True, botflag=False, maxTries=9)
		except wikipedia.NoPage:
			UserTalkPage.put(msgText, u"du wurdest zum dritten Mal bestätigt", False, minorEdit=False, force=True, botflag=False, maxTries=9)


"""
  MAIN
  gogogo
"""
output(strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############",localtime()))
db = wppb.Database(database=pb_db_config.db_name)

generator = [wikipedia.Page(wikipedia.getSite(), workList)]
generator = pagegenerators.PreloadingGenerator(generator, pageNumber = 1, lookahead=1)
page = u""
# variables for concatenating a reasonable edit summary
commentLongAdded = u""
commentLongRefused = u""
commentLongNewUsers = u""
commentLongACKAlreadyIn = u""
commentLongNewAlreadyIn = u"" # for new users
commentShortAdded = 0
commentShortRefused = 0
commentShortNewUsers = 0
commentShortACKAlreadyIn = 0
commentShortNewAlreadyIn = 0 # for new users

for page in generator: print u"" # take last element of iterator
rawText = page.get()
#rawText = u"<noinclude>{{/}}</noinclude>\n{{Wikipedia:Persönliche Bekanntschaften/neuer Benutzer|Name=Eukus Testköñto|Zeit=15:54, 31. Mai 2011 (CEST)}}"
newRawText = rawText

if not page.canBeEdited():
   output(u"Seite gesperrt")
   wikipedia.stopme()

#print db.get_mw_user_id(u"Eukus Testköñto")
newUsers, newACKs = divideIntoTasks(rawText)
for currentUser in newUsers:
	userName, minutes, hours, day, month, year = currentUser
	timestamp = "%s-%02d-%02d %02d:%02d:00" % (year, month, day, minutes, hours)
	output(u"füge %s hinzu.. " % userName)
	output(u"timestamp " + timestamp)
	entry = newUserReplRegex % re.escape(userName)
	output(u"entry:" + entry)
	
	try:
		if not DONOTSAVEDB: db.add_user(userName, timestamp)
	except oursql.IntegrityError:
		# already in ... TODO change the edit comment
		output(u"user " + userName + " already in")
	newRawText = wikipedia.replaceExcept(newRawText, entry, u"", [u"comment", u"nowiki"])

	# build comments for edit summary
	if commentLongNewUsers != u"": commentLongNewUsers = commentLongNewUsers + u", "
	commentLongNewUsers = commentLongNewUsers + (u"[[User:%s|%s]]" % (currentUser[0], currentUser[0]))
	commentShortNewUsers = commentShortNewUsers + 1

for currentACK in newACKs:
	output(u"füge Bestätigung: %s >> %s (Kommentar: %s) am %s:%s, %s. %s %s hinzu.." % currentACK)
	entry = newACKReplRegex % (re.escape(currentACK[0]), re.escape(currentACK[1]))
	addConfirmation(db, currentACK)
	newRawText = wikipedia.replaceExcept(newRawText, entry, u"", [u"comment", u"nowiki"])
	# build comments for edit summary
	if commentLongAdded != u"": commentLongAdded = commentLongAdded + u", "
	commentLongAdded = commentLongAdded + u"[[User:%s|%s]] → [[User:%s|%s]]" % (currentACK[0], currentACK[0], currentACK[1], currentACK[1])
	commentShortAdded = commentShortAdded + 1
# Müll?
#	except NoSuchUser:
#		newRawText = wikipedia.replaceExcept(newRawText, entry, u"", [u"comment", u"nowiki"])
#		output(u"Berichte Fehler")
#		if not DONOTSAVE:
#			# write error to WP
#			MainTalkPage = wikipedia.Page(wikipedia.getSite(), u"Wikipedia_Diskussion:Persönliche Bekanntschaften/neue Anfragen")
#			errorText = u"\n==Fehler ~~~~~ ==\nBeim Versuch eine Bestätigung in die Datenbank zu übertragen wurde ein Fehler festgestellt. Die Anfrage war: [[Benutzer:%s]] bestätigt [[Benutzer:%s]], mit Kommentar \"%s\" am %s:%s %s.%s.%s. Benutzer wurde nicht gefunden. --~~~~" % (currentACK)
#			try:
#				MainTalkPage.put(MainTalkPage.get() + errorText, u"Berichte Fehler", False, minorEdit=False, force=True)
#			except wikipedia.NoPage:
#				MainTalkPage.put(errorText, u"Berichte Fehler", False, minorEdit=False, force=True)
#				continue # ignore
#			# build comments for edit summary
#			if commentLongRefused != u"": commentLongRefused = commentLongRefused + u", "
#			commentLongRefused = commentLongRefused + u"[[User:%s|%s]] → [[User:%s|%s]]" % (currentACK[0], currentACK[0], currentACK[1], currentACK[1])
#			commentShortRefused = commentShortRefused + 1
#		continue
#	except ACKalreadyIn:
#		newRawText = wikipedia.replaceExcept(newRawText, entry, u"", [u"comment", u"nowiki"])
#		output(u"Doppelte Bestätigung ignoriert")
#		
#		# build comments for edit summary
#		if commentLongACKAlreadyIn != u"": commentLongACKAlreadyIn = commentLongACKAlreadyIn + u", "
#		commentLongACKAlreadyIn = commentLongACKAlreadyIn + u"[[User:%s|%s]] → [[User:%s|%s]]" % (currentACK[0], currentACK[0], currentACK[1], currentACK[1])
#		commentShortACKAlreadyIn = commentShortACKAlreadyIn + 1
#		continue
#	except illegalACK:
#		newRawText = wikipedia.replaceExcept(newRawText, entry, u"", [u"comment", u"nowiki"])
#		output(u"darf noch nicht bestätigen")
#		if not DONOTSAVE:
#		  # write error to WP
#		  middleText = u"Du hast vor ein paar Minuten auf [[Wikipedia:Persönliche_Bekanntschaften/neue Anfragen]] einen anderen Benutzer bestätigt. Momentan darfst du noch nicht bestätigen, weil du selber noch keine drei Bestätigungen erhalten hast. Sobald du diese erhalten hast, bekommst du eine Nachricht von mir auf deine Diskussionsseite."
#		  errorText = u"\n==[[Wikipedia:Persönliche Bekanntschaften]] ==\nHallo " + currentACK[0] + u".\n" + middleText + u" Bei Fragen wende dich [[Wikipedia Diskussion:Persönliche Bekanntschaften|hier]] hin. Gruß --~~~~"
#		  if not isIn(newRawText, middleText):
#			UserTalkPage = wikipedia.Page(wikipedia.getSite(), u"Benutzer_Diskussion:" + currentACK[0])
#			if DONOTSAVE: continue
#			try:
#				UserTalkPage.put(UserTalkPage.get() + errorText, u"du darfst noch nicht bestätigen", False, minorEdit=False, force=True, botflag=False, maxTries=9)
#			except wikipedia.NoPage:
#				UserTalkPage.put(errorText, u"du darfst noch nicht bestätigen", False, minorEdit=False, force=True, botflag=False, maxTries=9)
#				continue # ignore
#
#		# build comments for edit summary
#		if commentLongRefused != u"": commentLongRefused = commentLongRefused + u", "
#		commentLongRefused = commentLongRefused + u"[[User:%s|%s]] → [[User:%s|%s]]" % (currentACK[0], currentACK[0], currentACK[1], currentACK[1])
#		commentShortRefused = commentShortRefused + 1
#		continue

##### edit comments
editSummary = u"In Datenbank übertragen:"
commentPreAdded = u" Bestätigungen: "
commentPreRefused = u" abgelehnt: " # TODO clean up, or remove this...
commentPreNewUsers = u" neue(r) Benutzer: "
commentPreACKAlreadyIn = u" Bestätigungen schon vorhanden: "
commentPreNewAlreadyIn = u" Benutzer schon hinzugefügt: "

commentLong = editSummary
if commentLongAdded != u"":		commentLong = commentLong + commentPreAdded + commentLongAdded
if commentLongRefused != u"":		commentLong = commentLong + commentPreRefused + commentLongRefused
if commentLongACKAlreadyIn != u"":	commentLong = commentLong + commentPreACKAlreadyIn + commentLongACKAlreadyIn
if commentLongNewUsers != u"":		commentLong = commentLong + commentPreNewUsers + commentLongNewUsers
if commentLongNewAlreadyIn != u"":	commentLong = commentLong + commentPreNewAlreadyIn + commentLongNewAlreadyIn

commentShort = editSummary
if commentShortAdded != 0:		commentShort = commentShort + commentPreAdded + str(commentShortAdded)
if commentShortRefused != 0:		commentShort = commentShort + commentPreRefused + str(commentShortRefused)
if commentShortACKAlreadyIn != 0:	commentShort = commentShort + commentPreACKAlreadyIn + str(commentShortACKAlreadyIn)
if commentShortNewUsers != 0:		commentShort = commentShort + commentPreNewUsers + str(commentShortNewUsers)
if commentShortNewAlreadyIn != 0:	commentShort = commentShort + commentPreNewAlreadyIn + str(commentShortNewAlreadyIn)

if (len(commentLong) > 200):
	editSummary = commentShort
else:
	editSummary = commentLong

## update wikipedia: delete requests
if newRawText != rawText or (time.localtime()[3] in [3,15] and time.localtime()[4] in [0,1,2,3,4,5,6,7,8,9]):
	output(u"Anfragen:")
	wikipedia.showDiff(rawText, newRawText)
	if not DONOTSAVE:
		page.put(newRawText, editSummary, False, False, True)
	writeUserListToWikipedia(db, commentLongNewUsers)
	output(u"Zusammenfassung: " + editSummary + u"\n")
else:
	output(u"nichts zu tun")
	# write userlist 2 times a day
	if True or time.localtime()[3] in [3,15] and time.localtime()[4] in [0,1,2,3,4,5,6,7,8,9]:
		writeUserListToWikipedia(db, commentLongNewUsers)
