#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
	Wikipedia-pybot-framework is needed!
"""
import sys              # To not have wikipedia and this in one dir we'll import sys
import re               # Used for regular expressions
import os               # used for os.getcwd()
import wikipedia        # Wikipedia-pybot-framework
import pagegenerators
import locale			# German
from time import localtime, strftime, mktime    # strftime-Function and related
import time
ENV = "production" # for now there is no difference
if ENV == "trunc":
	sys.path.append('/home/euku/wppb/code/p_wppb/trunk/pyapi') # TODO make this a relative path
	sys.path.append('/home/euku/wppb/code/p_wppb/trunk/web/dynamic') # TODO make this a relative path
elif ENV == "production":
	sys.path.append('/home/euku/wppb/code/p_wppb/branches/production/pyapi') # TODO make this a relative path
	sys.path.append('/home/euku/wppb/code/p_wppb/branches/production/web/dynamic') # TODO make this a relative path
import wppb
import pb_db_config

wpOptInList = u"Wikipedia:Persönliche Bekanntschaften/Opt-in: Benachrichtigungen"
wpOptInListRegEx = u"\[\[(?:[uU]ser|[bB]enutzer)\:(?P<username>[^\|\]]+)(?:\|[^\]]+)?\]\]"
localLogFile = os.getcwd() + strftime("/logs/pb-info-bot-%Y-%m.log",localtime())

# debugging
DONOTSAVE = False # if True => no changes will be made on Wikipedia
diffDays = 1 # to check e.g. yesterday set this to 1. Attention to the first day of a month! It doesn't work.

def output(text):
	fd = open(localLogFile, 'a')
	writeMe = text + u"\n" 
	writeMe = writeMe.encode('utf-8')
	fd.write(writeMe)
	fd.close()
	wikipedia.output(text)

"""
	opt-in list
"""
def usersToCheck():
	optInPage = wikipedia.Page(wikipedia.getSite(), wpOptInList)
	optInRawText = optInPage.get()

	p = re.compile(wpOptInListRegEx, re.UNICODE)
	userIterator = p.finditer(optInRawText)
	result = []
	for user in userIterator:
		# "_" is the same as " " for Wikipedia URls
		result.append(wikipedia.replaceExcept(user.group('username'), u"_", u" ", []))
	return result


"""
  MAIN
"""
output(strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############",localtime()))
db = wppb.Database(database=pb_db_config.db_name)

# request list of all users that are opt-in
usersToCheck = usersToCheck()
output(u"%s users found in opt-in list" % len(usersToCheck))

todaysVerifications = db.get_yesterdays_confirmations_sorted_by_confirmed(day=1,delta=diffDays) # yesterday only
output(u"today %s confirmations were commited at all:" % len(todaysVerifications))
#print todaysVerifications

# who are the people the bot must write a message?
usersWaitingForMsg = []
for (was_confirmed_name, has_confirmed_name, cf_time) in todaysVerifications:
	if (not (was_confirmed_name in usersWaitingForMsg)) and was_confirmed_name in usersToCheck:
		usersWaitingForMsg.append(was_confirmed_name)

# send them a message
for userWaitingForMsg in usersWaitingForMsg:
	usersVeriedThisUser = []
	for (was_confirmed_name, has_confirmed_name, cf_time) in todaysVerifications:
		if was_confirmed_name == userWaitingForMsg:
			usersVeriedThisUser.append(has_confirmed_name)

	# write a message
	userTalkPage = wikipedia.Page(wikipedia.getSite(), u"Benutzer_Diskussion:" + userWaitingForMsg)
	try:
		userTalkPageRaw = userTalkPage.get()
	except wikipedia.NoPage:
		userTalkPageRaw = u""
	usersVeriedThisUserText = u""
	# concat a string with 'user1, user2, ... and userN'
	if len(usersVeriedThisUser) == 1:
		usersVeriedThisUserText = u"[[Benutzer:%s|]]" % usersVeriedThisUser[0]
	else:
		for u in usersVeriedThisUser[:len(usersVeriedThisUser)-1]:
			usersVeriedThisUserText += u", [[Benutzer:%s|]]" % u
		usersVeriedThisUserText += u" und [[Benutzer:%s|]]" % usersVeriedThisUser[len(usersVeriedThisUser)-1]
		# remove ', ' at the beginning
		usersVeriedThisUserText = usersVeriedThisUserText[2:]

	msgToUser = userTalkSummary = u""
	forThisDayText = ''
	if diffDays==0:
		forThisDayText = u"heute"
	elif diffDays == 1:
		forThisDayText = u"gestern"
	elif diffDays == 2:
		forThisDayText = u"vorgestern"
	else:
		forThisDayText = u"vor %s Tagen" % diffDays

	if len(usersVeriedThisUser) == 1:
		msgToUser = u"\n== neue Bestätigung am %s.%s.%s ==\nHallo! Du hast %s eine neue Bestätigung von %s bei [[WP:Persönliche Bekanntschaften|]] erhalten. [[Wikipedia:Persönliche Bekanntschaften/neue Anfragen|Hier]] kannst du selber bestätigen. Du bekommst diese Nachricht, weil du in [[Wikipedia:Persönliche Bekanntschaften/Opt-in: Benachrichtigungen|dieser Liste]] stehst. Gruß --~~~~" % (localtime()[2]-diffDays, localtime()[1], localtime()[0], forThisDayText, usersVeriedThisUserText)
		userTalkSummary = u"Neuer Abschnitt /* neue Bestätigung am %s.%s.%s */" % (localtime()[2]-diffDays, localtime()[1], localtime()[0])
	else:
		msgToUser = u"\n== neue Bestätigungen am %s.%s.%s ==\nHallo! Du hast %s neue Bestätigungen von %s bei [[WP:Persönliche Bekanntschaften|]] erhalten. [[Wikipedia:Persönliche Bekanntschaften/neue Anfragen|Hier]] kannst du selber bestätigen. Du bekommst diese Nachricht, weil du in [[Wikipedia:Persönliche Bekanntschaften/Opt-in: Benachrichtigungen|dieser Liste]] stehst. Gruß --~~~~" % (localtime()[2]-diffDays, localtime()[1], localtime()[0], forThisDayText, usersVeriedThisUserText)
		userTalkSummary = u"Neuer Abschnitt /* neue Bestätigungen am %s.%s.%s */" % (localtime()[2]-diffDays, localtime()[1], localtime()[0])

	output(u"Writing message to " + userWaitingForMsg + u"...")
	output(u"message: " + msgToUser)
	archiveHelp = u""
	if (isIn(userTalkPageRaw, u"\{\{\ *[Aa]utoarchiv")):
		archiveHelp = u" <!{{subst:ns:0}}-- Hilfe für den Auto-Archiv-Bot: ~~~~~ -->"
	elif (isIn(userTalkPageRaw, u"\{\{\ *[Aa]utoarchiv\-Erledigt")):
		archiveHelp = u"\n{{Erledigt|1=~~~~}}"
	if not DONOTSAVE:
		userTalkPage.put(userTalkPageRaw + msgToUser + archiveHelp, userTalkSummary, False, minorEdit=False, force=True, botflag=False, maxTries=2)
