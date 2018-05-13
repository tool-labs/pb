#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
	pywikibot framework is needed!
"""
import sys              # To not have wikipedia and this in one dir we'll import sys
import re               # Used for regular expressions
import os               # used for os.getcwd()
import pywikibot        # pywikibot framework
from pywikibot import config2, pagegenerators, Bot, textlib
import locale			# German
from time import localtime, strftime, mktime    # strftime-Function and related
import time
import oursql

sys.path.append('/data/project/pb/pb/pyapi') # TODO make this a relative path
import wppb
sys.path.append('/data/project/pb/pb/web/dynamic') # TODO make this a relative path
import pb_db_config

# templates and WP paths
tmplNewUser = u"Wikipedia:Persönliche Bekanntschaften/neuer Benutzer"
newUserRegex = u"\{\{" + tmplNewUser + u"\|Name=(?P<user>[^|]+)(?:\|Kommentar=.*)?\|Zeit=(?P<timeh>(?:[01]\d|2[0-3]))\:(?P<timemin>[0-5]\d)\,\ (?P<timed>[123]?\d)\.\ (?P<timemon>Jan\.|Feb\.|Mär\.|Apr\.|Mai|Jun\.|Jul\.|Aug\.|Sep\.|Okt\.|Nov\.|Dez\.)\ (?P<timeyear>2\d\d\d)\ \(CES?T\)\}\}"
newUserReplRegex = u"\{\{" + tmplNewUser + u"\|Name=%s(?:\|Kommentar=.*?)?\|Zeit=.+?\ 2\d\d\d\ \(CES?T\)\}\}[\n\r]*"
tmplNewACK = u"Wikipedia:Persönliche Bekanntschaften/neue Bestätigung"
newACKRegex = u"\{\{" + tmplNewACK + u"\|Bestätiger=(?P<certifier>[^|]+)\|Bestätigter=(?P<certified>[^|]+)\|Kommentar=(?P<comment>.*?)\|Zeit=(?P<timeh>(?:[01]\d|2[0-3]))\:(?P<timemin>[0-5]\d)\,\ (?P<timed>[123]?\d)\.\ (?P<timemon>Jan\.|Feb\.|Mär\.|Apr\.|Mai|Jun\.|Jul\.|Aug\.|Sep\.|Okt\.|Nov\.|Dez\.)\ (?P<timeyear>2\d\d\d)\ \(CES?T\)\}\}"
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
# OLD:
#	fd = open(localLogFile, 'a')
#	writeMe = text + u"\n" 
#	writeMe = writeMe.encode('utf-8')
#	fd.write(writeMe)
#	fd.close()
	pywikibot.output(text)


def writeUserListToWikipedia(db, editSummary):
	if editSummary == u'': editSummary = u"Aktualisiere Benutzerliste"

	# laad list
	userList = db.get_user_list_with_confirmations() 
	#print userList
	#############################################
	# prepare the raw user list for JavaScripts #
	#############################################
	# convert it to a string
	newRawText = u""
	for u, confirmationCount, part_since_timestamp in userList:
		# former and bannen users are already left out
		newRawText += u + u"\n"
	# save RAW-list
	page = pywikibot.Page(pywikibot.Site(), userRAWListPage)
	rawText = page.get()
	if newRawText != rawText + u"\n":
		output(u"RAW-Benutzerliste:")
		pywikibot.showDiff(rawText, newRawText)
	 	if not DONOTSAVE:
			page.put(newRawText, editSummary, False, minorEdit=True, force=True)

	#####################################
	# prepare user list for main page   #
	#####################################
	toc = u'{{WP:Persönliche Bekanntschaften/Infobox}}\n{{WP:Persönliche Bekanntschaften/Teilnehmerliste/Intro}}\nAngezeigt werden \'\'\'<span id="num-participants">' + str(len(userList)) + u'</span>\'\'\' Teilnehmer:\n'
	userTemplate = u'{{DB-Link|%s|%s|%s|%s}}'
	classTemplate1 = u'===%s===\n'
	classTemplate2 = u'\n'

	currentLetter = u"0–9"
	newRawText = toc + (classTemplate1 % currentLetter)
	for u, confirmationCount, part_since_timestamp in userList:
		# fill in sub headers
		if ((currentLetter == u"0–9") and (u[0] == u"A")):
			currentLetter = u"A"
			newRawText += classTemplate2 + (classTemplate1 % currentLetter)
		elif (currentLetter != u"0–9" and u[0] > currentLetter and u[0] <= u"Z"):
			currentLetter = u[0]
			newRawText += classTemplate2 + (classTemplate1 % currentLetter)
		verfStatus = u"u" if confirmationCount < 3 else u""
		inactiveStatus = u"" # TODO
		homewiki = u""#TODO
		newRawText += userTemplate % (u, verfStatus, inactiveStatus, homewiki)
	newRawText += classTemplate2
	# save it
	page = pywikibot.Page(pywikibot.Site(), userListPage)
	rawText = page.get()
	if newRawText != rawText + u"\n":
	   output(u"Teilnehmerliste:")
	   pywikibot.showDiff(rawText, newRawText)
	   if not DONOTSAVE:
		  page.put(newRawText, editSummary, False, minorEdit=True, force=True, botflag=False)
	
	######################
	# write new users    #
	######################
	# prepare new-user list for main page
	newUserList = db.get_latest_user_list_with_confirmations() 
	toc = u'<noinclude>{{WP:Persönliche Bekanntschaften/Teilnehmerliste/Intro}}</noinclude>\n== Neu dazugekommen ==\n'
	userTemplate = u'{{/Benutzer-Link|%s|%s|%s}} '

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
	page = pywikibot.Page(pywikibot.Site(), newUserListPage)
	rawText = page.get()
	if newRawText != rawText + u"\n":
	   output(u"Teilnehmerliste:")
	   pywikibot.showDiff(rawText, newRawText)
	   if not DONOTSAVE:
		  page.put(newRawText, editSummary, False, minorEdit=True, force=True, botflag=False)

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
def addConfirmation(db, certifier, certified, comment, year, month, day, hours, minutes):
	bestaetigerName = certifier
	bestaetigterName = certified

	bestaetigerID = -1
	bestaetigterID = -1
	bestaetigerCfCount = -1
	try:
		bestaetigerID  = db.get_user_by_name(bestaetigerName)[1]
		bestaetigterID = db.get_user_by_name(bestaetigterName)[1]
		bestaetigerCfCount = db.get_cf_count_by_confirmed(bestaetigerID)
	except TypeError:
		return

	if (bestaetigerCfCount < 3):
		return # user is not allowed

	###### write to DB
	output(u"send it to DB API...")
	timestamp = "%s-%02d-%02d %02d:%02d:00" % (year, month, day, hours, minutes)
	if not DONOTSAVEDB:
		try:
			db.add_confirmation(bestaetigerID, bestaetigterID, comment, timestamp)
		except oursql.IntegrityError:
			output("Bestaetigung schon vorhanden")
			return
	
	### check if 'bestaetigterName' is allowed to write ACKs now and leave a message on his/her talk page
	if db.get_cf_count_by_confirmed(bestaetigterID) == 3:
		# ok, write a message
		msgText = u"\n==[[Wikipedia:Persönliche Bekanntschaften]] ==\nHallo " + bestaetigterName + u".\nDu wurdest vor ein paar Minuten von " + bestaetigerName + u" bestätigt und hast damit insgesamt drei Bestätigungen. D.h. von nun an darfst du [[Wikipedia:Persönliche Bekanntschaften/neue Anfragen|selber Bestätigungen verteilen]] an Wikipedianer, die du persönlich kennengelernt hast. Bei Fragen wende dich [[Wikipedia Diskussion:Persönliche Bekanntschaften|hier]] hin. Gruß --~~~~"
		output(u"war unbestaetigt und darf nun selber bestaetigen")
		UserTalkPage = pywikibot.Page(pywikibot.Site(), u"Benutzer_Diskussion:" + bestaetigterName)
		if DONOTSAVE: return
		try:
			UserTalkPage.put(UserTalkPage.get() + msgText, u"du wurdest zum dritten Mal bestätigt", False, minorEdit=False, force=True, botflag=False)
		except pywikibot.NoPage:
			UserTalkPage.put(msgText, u"du wurdest zum dritten Mal bestätigt", False, minorEdit=False, force=True, botflag=False)


"""
  MAIN
"""
class PBBot(Bot):
	def __init__(self, isForceMode=False):
		self._site = pywikibot.Site()
		self.isForceMode = pywikibot.bot.handleArgs()
        
	def run(self):
		output(strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############",localtime()))
		db = wppb.Database(database=pb_db_config.db_name)

		generator = [pywikibot.Page(self._site, workList)]
		generator = pagegenerators.PreloadingGenerator(generator, step = 1, lookahead=1)
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
		newRawText = rawText

		if not page.canBeEdited():
		   output(u"Seite gesperrt")
		   pywikibot.stopme()

		newUsers, newACKs = divideIntoTasks(rawText)
		seenUsers = []
		for currentName, minutes, hours, day, month, year in newUsers:
			if currentName in seenUsers:
				output(u"überspringe %s weil schon enthalten" % currentName)
				continue

			timestamp = "%s-%02d-%02d %02d:%02d:00" % (year, month, day, hours, minutes)
			output(u"füge %s hinzu.. "  % currentName)
			entry = newUserReplRegex % re.escape(currentName)

			try:
				if not DONOTSAVEDB: db.add_user(currentName, timestamp)
			except oursql.IntegrityError:
				# already in ... TODO change the edit comment
				output(u"user " + currentName + " already in")
			except oursql.CollatedWarningsError:
				# already in ... TODO change the edit comment
				output(u"user " + currentName + " already in")
			newRawText = textlib.replaceExcept(newRawText, entry, u"", [u"comment", u"nowiki"])

			# build comments for edit summary
			if commentLongNewUsers != u"": commentLongNewUsers = commentLongNewUsers + u", "
			commentLongNewUsers = commentLongNewUsers + (u"[[User:%s|%s]]" % (currentName, currentName))
			commentShortNewUsers = commentShortNewUsers + 1

		doNotRemoveWikiText = False
		for currentACK in newACKs:
			certifier, certified, comment, minutes, hours, day, month, year = currentACK
			timestamp = "%s-%02d-%02d %02d:%02d:00" % (year, month, day, hours, minutes)
			output(u"füge Bestätigung: %s >> %s (Kommentar: %s) am %s hinzu.." % (certifier, certified, comment, timestamp))
			entry = newACKReplRegex % (re.escape(certifier), re.escape(certified))
			try:
				addConfirmation(db, certifier, certified, comment, year, month, day, hours, minutes)
			except oursql.PermissionsError: # WORKAROUND wir koennen nicht sicher sein, dass die Bestaetigungen wirklich ankamen, darum entferne sie erst beim naechsten Mal, wenn es sicher ist!
				doNotRemoveWikiText = True
			newRawText = textlib.replaceExcept(newRawText, entry, u"", [u"comment", u"nowiki"])
			# build comments for edit summary
			if commentLongAdded != u"": commentLongAdded = commentLongAdded + u", "
			commentLongAdded = commentLongAdded + u"[[User:%s|%s]] → [[User:%s|%s]]" % (certifier, certifier, certified, certified)
			commentShortAdded = commentShortAdded + 1

		if doNotRemoveWikiText:
			output("Bestaetigungen versucht hinzuzufuegen, aber wegen oursql.PermissionsError nicht von der WP-Seite entfernt!")
			return # ende hier
		##### edit comments
		editSummary = u""
		commentPreAdded = u" Bestätigungen: "
		commentPreNewUsers = u" neue(r) Benutzer: "
		commentPreACKAlreadyIn = u" Bestätigungen schon vorhanden: "
		commentPreNewAlreadyIn = u" Benutzer schon hinzugefügt: "

		commentLong = editSummary
		if commentLongAdded != u"":		commentLong = commentLong + commentPreAdded + commentLongAdded
		if commentLongACKAlreadyIn != u"":	commentLong = commentLong + commentPreACKAlreadyIn + commentLongACKAlreadyIn
		if commentLongNewUsers != u"":		commentLong = commentLong + commentPreNewUsers + commentLongNewUsers
		if commentLongNewAlreadyIn != u"":	commentLong = commentLong + commentPreNewAlreadyIn + commentLongNewAlreadyIn

		commentShort = editSummary
		if commentShortAdded != 0:		commentShort = commentShort + commentPreAdded + str(commentShortAdded)
		if commentShortACKAlreadyIn != 0:	commentShort = commentShort + commentPreACKAlreadyIn + str(commentShortACKAlreadyIn)
		if commentShortNewUsers != 0:		commentShort = commentShort + commentPreNewUsers + str(commentShortNewUsers)
		if commentShortNewAlreadyIn != 0:	commentShort = commentShort + commentPreNewAlreadyIn + str(commentShortNewAlreadyIn)

		if (len(commentLong) > 200):
			editSummary = commentShort
		else:
			editSummary = commentLong

		## update wikipedia: delete requests
		if self.isForceMode or newRawText != rawText:
			output(u"Anfragen:")
			pywikibot.showDiff(rawText, newRawText)
			if not DONOTSAVE:
				page.put(newRawText, u"In Datenbank übertragen: " + editSummary, False, False, True)
			writeUserListToWikipedia(db, editSummary)
			output(u"Zusammenfassung: " + editSummary + u"\n")
		else:
			output(u"nichts zu tun")
			# write userlist 4 times per day
			if time.localtime()[3] in [3,15] and time.localtime()[4] in [0,1,2,3,4,5,6,7,8,9]:
				writeUserListToWikipedia(db, editSummary)

# start here
bot = PBBot()
bot.run()
