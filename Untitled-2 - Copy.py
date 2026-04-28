"""
You must have an AWS account to use the Amazon Connect CTI Adapter.
Downloading and/or using the Amazon Connect CTI Adapter is subject to the terms of the AWS Customer Agreement,
AWS Service Terms, and AWS Privacy Notice.

© 2017, Amazon Web Services, Inc. or its affiliates. All rights reserved.

NOTE:  Other license terms may apply to certain, identified software components
contained within or distributed with the Amazon Connect CTI Adapter if such terms are
included in the LibPhoneNumber-js and Salesforce Open CTI. For such identified components,
such other license terms will then apply in lieu of the terms above.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import logging, os, json, phonenumbers
from salesforce import Salesforce
from datetime import datetime, timedelta
from sf_util import parse_date, text_replace_string
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(os.environ["LOGGING_LEVEL"]))

def removekey(d, key):
    r = dict(d)
    del r[key]
    return r

def lambda_handler(event, context):
  logger.info("event: %s" % json.dumps(event))
  sf = Salesforce()
  sf.sign_in()

  sf_operation = str(event['Details']['Parameters']['sf_operation'])
  parameters = dict(event['Details']['Parameters'])
  del parameters['sf_operation']
  event['Details']['Parameters'] = parameters

  if(sf_operation == "lookup"):
    resp = lookup(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "create"):
    resp = create(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "update"):
    resp = update(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "phoneLookup"):
    resp = phoneLookup(sf, event['Details']['Parameters']['sf_phone'], event['Details']['Parameters']['sf_fields'])
  elif (sf_operation == "phoneQuery"):
        resp = phoneQuery(sf, event['Details']['Parameters']['sf_phone'], event['Details']['Parameters']['sf_fields'])
  elif (sf_operation == "delete"):
    resp = delete(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "lookup_all"):
    resp = lookup_all(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "query"):
    resp = query(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "queryOne"):
    resp = queryOne(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "createChatterPost"): 
    resp = createChatterPost(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "createChatterComment"):
    resp = createChatterComment(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "search"):
    resp = search(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "searchOne"):
    resp = searchOne(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "createCase"):
        resp = createCase(sf=sf, **event['Details']['Parameters'])
  elif (sf_operation == "unauthCaseLookup"):
        resp = unauthCaseLookup(sf, event['Details']['Parameters']['sf_fields'], event['Details']['Parameters']['LookupNumber'], event['Details']['Parameters']['digits'])
  elif (sf_operation == "unauthOrderLookup"):
        resp = unauthOrderLookup(sf, event['Details']['Parameters']['sf_fields'], event['Details']['Parameters']['LookupNumber'])      
  elif (sf_operation == "caseOrderLookup"):
    resp = caseOrderLookup(sf=sf,
                            hasMultipleUsers=event['Details']['ContactData']['Attributes']['hasMultipleUsers'],
                            usernameList=event['Details']['ContactData']['Attributes']['multipleUsersList'],
                            userAccountList=event['Details']['ContactData']['Attributes']['userAccountList'],
                            **event['Details']['Parameters'])  
  elif (sf_operation == "updateCallRating"):
    print("-------------------- Update Call Rating -----------------------------")
    id = taskLookup(sf=sf, sf_callobject=event['Details']['Parameters']['sf_callobject'])
    if (id != ''):
      event['Details']['Parameters']['sf_id'] = id
      del event['Details']['Parameters']['sf_callobject']
      resp = update(sf=sf, **event['Details']['Parameters'])
  else:
    msg = "sf_operation unknown"
    logger.error(msg)
    raise Exception(msg)
  
  logger.info("result: %s" % resp)
  return resp

# ****WARNING**** -- this function will be deprecated in future versions of the integration; please use search/searchOne.
def lookup(sf, sf_object, sf_fields, **kwargs):
  print("-------------------- lookup -----------------------------")
  where = " AND ".join([where_parser(*item) for item in kwargs.items()])
  query = "SELECT %s FROM %s WHERE %s" % (sf_fields, sf_object, where)
  print("Query : " + query)
  records = sf.query(query=query)
  count = len(records)
  result = records[0] if count > 0 else {}
  result['sf_count'] = count
  print(result)
  return result

def getGSDlookup(sf, id):
    case_id = "'" + id + "'"
    query = "SELECT Pending_Input_Case_Comment__c FROM Case WHERE id=%s" % (case_id)
    print("Query : " + query)
    records = sf.query(query=query)
    return records[0]['Pending_Input_Case_Comment__c']
    
def where_parser(key, value):
  if key.lower() in ['mobilephone', 'homephone']:
    return "%s LIKE '%%%s%%%s%%%s%%'" % (key, value[-10:-7], value[-7:-4], value[-4:])
    
  if "%" in value:
    return "%s LIKE '%s'" % (key, value)

  return "%s='%s'" % (key, value)

def create(sf, sf_object, **kwargs):
  print("-------------------- create -----------------------------")
  data = {k:parse_date(v) for k,v in kwargs.items()}
  print(data)
  return {'Id':sf.create(sobject=sf_object, data=data)}

def update(sf, sf_object, sf_id, **kwargs):
  print("-------------------- update -----------------------------")
  data = {k:parse_date(v) for k,v in kwargs.items()}
  print(data)
  return {'Status':sf.update(sobject=sf_object, sobj_id=sf_id, data=data)}

def phoneLookup(sf, phone, sf_fields):
  print("-------------------- phone lookup -----------------------------")
  print('Before phone formatting : ' + phone[0])

  if phone[0] != '+' and len(phone) == 10:
    phone = '+1' + phone

  if phone[0] != '+':
    phone = '+' + phone

  phone_national = str(phonenumbers.parse(phone, None).national_number)
  print('Phone national : ' + phone_national)

  param = {
    'q':phone_national,
    'sobjects': [{"name":"Contact"}],
    'fields': sf_fields.split(', ')
  }
  records = sf.parameterizedSearch(param)
  userAccountList = {}
  multipleUsers = {}
  usernameList = ''
  Email = '' #
  count = len(records)
  portalUsernameCount = 0
  contactId=''
  result = {
    'isNumInSalesForce': 'false',
    'Phone': None
  }

  count = len(records)
  
  if (count > 0):
    print(records)
    for record in records:
      phoneKeys = ['Phone', 'HomePhone', 'Office_Phone__c', 'MobilePhone', 'OtherPhone']
      phoneNumbers = list(map(lambda key: record.get(key, None), phoneKeys))


      sfPhone = next((number for number in phoneNumbers if number is not None), None)
      if (sfPhone is not None and result['Phone'] is None):
        result['Phone'] = sfPhone

      if (sfPhone is not None):
        if (record['Portal_User_Name__c'] is not None):
          if (record['Inactive__c'] is not True):
            result['isNumInSalesForce'] = 'true'
            userAccountList[record['Portal_User_Name__c']] = {}
            userAccountList[record['Portal_User_Name__c']]["accountId"] = record['Account']["Id"]
            userAccountList[record['Portal_User_Name__c']]["parentAccountId"] = record['Account']["Ultimate_Parent_AccountId__c"]
            userAccountList[record['Portal_User_Name__c']]["accountType"] = record['Account']["Sales_Program_Type__c"]
            userAccountList[record['Portal_User_Name__c']]["accountNumber"] = record['Account']["AccountNumber"]
            userAccountList[record['Portal_User_Name__c']]["GSD_Category__c"] = record['Account']["GSD_Category__c"]
            userAccountList[record['Portal_User_Name__c']]["Source__c"] = record['Account']["Source__c"]
            if (usernameList == ''):
              usernameList = record['Portal_User_Name__c']
              Email = record['Email'] #ismail
              multipleUsers = record['Name']
              contactId=record['Id']
            else:
              usernameList = usernameList + ' ' + record['Portal_User_Name__c']
              multipleUsers = multipleUsers + ', ' + record['Name']
            portalUsernameCount += 1  
  else:
    print('phone number not found in salesforce, falling back to query')
    print('Calling phone query ==>')
    return phoneQuery(sf, phone, sf_fields)

  result['contactId']=contactId
  result['usernameList'] = usernameList
  result['Email'] = Email #ismail
  result['sf_count'] = portalUsernameCount
  result['userAccountList'] = json.dumps(userAccountList)
  result['multipleUsers'] = json.dumps(multipleUsers)
  return result
  
def phoneQuery(sf, phone, sf_fields):
  print("-------------------- phone Query -----------------------------")
  print(f'Querying for phone: {phone}, with fields: {sf_fields}')

  searchTerm = buildSearchTermForPhone(phone)

  print(f'Search term for phone: {searchTerm}')

  query = f'''
    FIND {{ {searchTerm} }} IN Phone Fields
    RETURNING Contact( {sf_fields} )
  '''

  print(f'Performing search: {query}')

  records = sf.search(query=query)

  print(f'Search results: {records}')

  usernameList = ''
  count = len(records)
  portalUsernameCount = 0
  result = {
    'isNumInSalesForce': 'false',
    'Phone': None
  }
  userAccountList = {}
  multipleUsers = {}
  if (count > 0):
    print(records)
    for record in records:
      phoneKeys = ['Phone', 'HomePhone', 'Office_Phone__c', 'MobilePhone', 'OtherPhone']
      phoneNumbers = list(map(lambda key: record.get(key, None), phoneKeys))


      sfPhone = next((number for number in phoneNumbers if number is not None), None)
      if (sfPhone is not None and result['Phone'] is None):
        result['Phone'] = sfPhone

      if (sfPhone is not None):
        if (record['Portal_User_Name__c'] is not None):
          if (record['Inactive__c'] is not True):
            result['isNumInSalesForce'] = 'true'
            userAccountList[record['Portal_User_Name__c']] = {}
            userAccountList[record['Portal_User_Name__c']]["accountId"] = record['Account']["Id"]
            userAccountList[record['Portal_User_Name__c']]["parentAccountId"] = record['Account']["Ultimate_Parent_AccountId__c"]
            userAccountList[record['Portal_User_Name__c']]["accountType"] = record['Account']["Sales_Program_Type__c"]
            userAccountList[record['Portal_User_Name__c']]["accountNumber"] = record['Account']["AccountNumber"]
            userAccountList[record['Portal_User_Name__c']]["GSD_Category__c"] = record['Account']["GSD_Category__c"]
            userAccountList[record['Portal_User_Name__c']]["Source__c"] = record['Account']["Source__c"]
            if (usernameList == ''):
              usernameList = record['Portal_User_Name__c'] 
              multipleUsers = record['Name']
            else:
              usernameList = usernameList + ' ' + record['Portal_User_Name__c']
              multipleUsers = multipleUsers + ', ' + record['Name']
            portalUsernameCount += 1
  else:
    print('phone number not found in salesforce')
    result = {
      'isNumInSalesForce': 'false'
    }

  result['usernameList'] = usernameList
  result['userAccountList'] = json.dumps(userAccountList)
  result['sf_count'] = portalUsernameCount
  result['multipleUsers'] = json.dumps(multipleUsers)
  return result

def buildSearchTermForPhone(phone):
  # example source Phone# "+14435551234"
  # target Phone#         "*44*3*5*55*1234"
  if (len(phone) == 0):
    return phone

  if (phone[0] == '+'):
    phone = phone[1:]

  if (phone[0] == '1'):
    phone = phone[1:]

  originalLength = len(phone)
  if (originalLength > 4):
    phone = phone[:originalLength - 4] + '*' + phone[originalLength - 4:]
  if (originalLength > 6):
    phone = phone[:originalLength - 6] + '*' + phone[originalLength - 6:]
  if (originalLength > 7):
    phone = phone[:originalLength - 7] + '*' + phone[originalLength - 7:]
  if (originalLength > 8):
    phone = phone[:originalLength - 8] + '*' + phone[originalLength - 8:]
  if (originalLength > 10):
    phone = phone[:originalLength - 10] + '*' + phone[originalLength - 10:]
  if (phone[0] != '*'):
    phone = '*' + phone

  return phone

def createCase(sf, sf_object, CallContext, **kwargs):
  print("-------------------- create case -----------------------------")
  data = {k:parse_date(v) for k,v in kwargs.items()}
  #data['Subject'] = CallContext
  #print("Data : " + data)
  contactId = sf.create(sobject=sf_object, data=data)
  print("Created case Id : " + contactId)
  return {
    "caseNumber": contactId,
  }  

def delete(sf, sf_object, sf_id):
  return {'Response': sf.delete(sobject=sf_object, sobject_id=sf_id)}

# ****WARNING**** -- this function will be deprecated in future versions of the integration; please use search/searchOne.
def lookup_all(sf, sf_object, sf_fields, **kwargs):
  where = " AND ".join([where_parser(*item) for item in kwargs.items()])
  query_filter = (" WHERE" + where) if kwargs.__len__() > 0 else ''
  query = "SELECT %s FROM %s  %s" % (sf_fields, sf_object, query_filter)
  records = sf.query(query=query)
  return records

# ****WARNING**** -- this function will be deprecated in future versions of the integration; please use search/searchOne.
def query(sf, query, **kwargs):
  for key, value in kwargs.items():
    logger.info("Replacing [%s] with [%s] in [%s]" % (key, value, query))
    query = query.replace(key, value)

  records = sf.query(query=query)
  count = len(records)
  result = {}
  
  if count > 0:
    recordArray = []
    for record in records :
      recordArray.append(flatten_json(record))
  
    result['sf_records'] = recordArray
    print(result)
  else:
    result['sf_records'] = []

  result['sf_count'] = count
  return result

# ****WARNING**** -- this function will be deprecated in future versions of the integration; please use search/searchOne.
def queryOne(sf, query, **kwargs):
  for key, value in kwargs.items():
    logger.info("Replacing [%s] with [%s] in [%s]" % (key, value, query))
    query = query.replace(key, value)

  records = sf.query(query=query)
  count = len(records)
  result = flatten_json(records[0]) if count == 1 else {}
  result['sf_count'] = count
  return result

def createChatterPost(sf, sf_feedElementType, sf_subjectId, sf_messageType, sf_message, **kwargs):
  formatted_message = text_replace_string(sf_message, kwargs)
  logger.info('Formatted message: %s', formatted_message)

  data = {'sf_feedElementType': sf_feedElementType,
          'sf_subjectId': sf_subjectId,
          'sf_messageType': sf_messageType,
          'sf_message': formatted_message,
          'sf_mention': kwargs.get('sf_mention','')}
    
  return {'Id': sf.createChatterPost(data)}


def createChatterComment(sf, sf_feedElementId, sf_commentType, sf_commentMessage, **kwargs):
  formatted_message = text_replace_string(sf_commentMessage, kwargs)
  logger.info('Formatted message: %s', formatted_message)

  data = {'sf_feedElementId': sf_feedElementId,
          'sf_commentType': sf_commentType,
          'sf_commentMessage': formatted_message}

  return {'Id': sf.createChatterComment(sfeedElementId=sf_feedElementId, data=data)}

def search(sf, q, sf_fields, sf_object, where="", overallLimit=100, **kwargs):
  obj = [ { 'name': sf_object } ]
  if where:
    obj[0]['where'] = where
  
  data = {
    'q':q,
    'fields': sf_fields.split(', '),
    'sobjects': obj,
    'overallLimit': overallLimit
  }
  records = sf.parameterizedSearch(data=data)

  count = len(records)
  result = {}
  
  if count > 0:
    recordArray = []
    for record in records:
      recordArray.append(flatten_json(record))

    result['sf_records'] = recordArray
  else:
    result['sf_records'] = []

  result['sf_count'] = count
  return result

def searchOne(sf, q, sf_fields, sf_object, where="", **kwargs):
  obj = [ { 'name': sf_object } ]
  if where:
    obj[0]['where'] = where
  
  data = {
    'q':q,
    'fields': sf_fields.split(', '),
    'sobjects': obj
  }
  records = sf.parameterizedSearch(data=data)
  count = len(records)
  result = flatten_json(records[0]) if count == 1 else {}
  result['sf_count'] = count
  return result

def flatten_json(nested_json):
  out = {}
    
  def flatten(x, name=''):
    if type(x) is dict:
      for a in x:
        flatten(x[a], name + a + '.')
    elif type(x) is list:
      i = 0
      for a in x: 
        flatten(a, name)
        i += 1
    else:
      out[name[:-1]] = x

  flatten(nested_json)
  return out 

def taskLookup(sf, sf_callobject):
  print("--------------- taskLookup -------------------------")
  callObjectParam = "'" + sf_callobject + "'"
  getAllCaseQuery = "SELECT ID FROM TASK WHERE CALLOBJECT = %s" % (callObjectParam)
  print("Query : " + getAllCaseQuery)
  records = sf.query(query=getAllCaseQuery)
  count = len(records)

  if (count > 0):
      result = records[0]
      #print("return : " + result)
      return result['Id']
  print("return : ''")
  return ''

def caseOrderLookup(sf, hasMultipleUsers,userAccountList, usernameList, sf_object, sf_case_fields, sf_lookUp_number, sf_contact,sf_order_fields, RecordTypeId):
  print("------------------------ caseOrderLookup --------------------------- ")
  caseResultValue = {}
  print("Username list : " + usernameList)
  
  userList = str(usernameList).split()
  print("Calling Case lookup == >")
  caseResult = caseLookup(sf, sf_object, sf_case_fields, sf_lookUp_number,userAccountList=userAccountList, userList=userList, RecordTypeId=RecordTypeId)
  if (caseResult['sf_count'] > 0):
    return caseResult
    
  else:
    print("Calling Order lookup == >")
    orderResult = orderLookup(sf, sf_object, sf_case_fields, sf_lookUp_number, userAccountList=userAccountList, userList=userList, RecordTypeId=RecordTypeId)
    return orderResult
  
def orderLookup(sf, sf_object, sf_fields, sf_orderNumber, userAccountList="", userList="", sf_contact="", RecordTypeId=""):
  result = {}
  result['Id'] = 0
  orderCount = 0

  accountsRecords = json.loads(userAccountList)
  print(accountsRecords)

  for user in userList:
    print("********* => " + user)
    accounts = accountsRecords[user]
    print(accounts)
    parentAccount = accounts['accountId']
    rootAccount = accounts['parentAccountId']

    getAllCaseQuery = ""
    if (rootAccount):
        getAllCaseQuery = """SELECT %s FROM %s Ca WHERE (Ca.Account.Id = '%s' OR Ca.Account.Id = '%s' OR Ca.Account.Ultimate_Parent_AccountId__c = '%s' OR Ca.Account.Ultimate_Parent_AccountId__c = '%s') AND RecordTypeId='%s' AND (Ca.Siebel_Order_Number__c like '%%%s') AND CreatedDate = LAST_N_DAYS:92""" % (sf_fields, sf_object, parentAccount, rootAccount, parentAccount, rootAccount, RecordTypeId, sf_orderNumber)
    else:
        getAllCaseQuery = """SELECT %s FROM %s Ca WHERE (Ca.Account.Id = '%s' OR Ca.Account.Ultimate_Parent_AccountId__c = '%s') AND RecordTypeId='%s' AND (Ca.Siebel_Order_Number__c like '%%%s') AND CreatedDate = LAST_N_DAYS:92""" % (sf_fields, sf_object, parentAccount, parentAccount, RecordTypeId, sf_orderNumber)
    print(getAllCaseQuery)

    records = sf.query(query=getAllCaseQuery)
    print(records)

    if (len(records) > 0):
      print("HEY")
      print(result)
      if(result['Id'] == records[0]['Id']):
            print("same order number")
            continue
      result = records[0]
      result['isCaseOrderFound'] = 'true'
      orderCount = orderCount + len(records)
      result['sf_count'] = orderCount
      if(orderCount > 1):
        print("order count more than 1")
        result['sf_count'] = orderCount
        return result

    # try:
    #     # type = result[accounts['accountId']]['Type']
    #     # result[accounts['accountId']]['Type'] = data[type]
    #     type = result['Type']
    #     result['Type'] = data[type]
    # except KeyError:
    #     print('No type conversion is required.')
    # print("************************************************") 

  result['sf_count'] = orderCount
  return result


def caseLookup(sf, sf_object, sf_fields, sf_casenumber, userAccountList="", userList="", sf_contact="", RecordTypeId=""):
    result = {}
    caseCount = 0
    result['Id'] = 0
    accountsRecords = json.loads(userAccountList)
    print("Account Records : ")
    print(accountsRecords)

    for user in userList:
      print("********* => " + user)
      accounts = accountsRecords[user]
      print(accounts)
      parentAccount = accounts['accountId']
      rootAccount = accounts['parentAccountId']

      getAllCaseQuery = ""
      if (rootAccount):
          getAllCaseQuery = """SELECT %s FROM %s Ca WHERE (Ca.Account.Id = '%s' OR Ca.Account.Id = '%s' OR Ca.Account.Ultimate_Parent_AccountId__c = '%s' OR Ca.Account.Ultimate_Parent_AccountId__c = '%s') AND RecordTypeId='%s' AND Ca.CaseNumber like '%%%s' AND CreatedDate = LAST_N_DAYS:92""" % (sf_fields, sf_object, parentAccount, rootAccount, parentAccount, rootAccount, RecordTypeId, sf_casenumber)
      else:
          getAllCaseQuery = """SELECT %s FROM %s Ca WHERE (Ca.Account.Id = '%s' OR Ca.Account.Ultimate_Parent_AccountId__c = '%s') AND RecordTypeId='%s' AND Ca.CaseNumber like '%%%s' AND CreatedDate = LAST_N_DAYS:92""" % (sf_fields, sf_object, parentAccount, rootAccount, RecordTypeId, sf_casenumber)
      
      print(getAllCaseQuery)

      records = sf.query(query=getAllCaseQuery)
      print(records)

      if (len(records) > 0):
        if(result['Id'] == records[0]['Id']):
            print("same case number")
            continue
        result = records[0]
        result['isCaseOrderFound'] = 'true'
        caseCount = caseCount + len(records)
        result['sf_count'] = caseCount
        print(result)
        if(caseCount > 1):
            print("sf_count more than 1")
            result['sf_count'] = caseCount
            return result
        print("************************************************")    

      # try:
      #     # type = result[accounts['accountId']]['Type']
      #     # result[accounts['accountId']]['Type'] = data[type]
      #     type = result['Type']
      #     result['Type'] = data[type]
      # except KeyError:
      #     print('No type conversion is required.')

    result['sf_count'] = caseCount
    return result
    

def unauthCaseLookup(sf, sf_fields, LookupNumber, digits):
  result = {}
  print("--------------- UnauthCaseLookup -------------------------")
  if (digits == "isSevenDigits"): 
    getAllCaseQuery = "SELECT %s FROM Case WHERE CaseNumber = '0%s'" % (sf_fields, LookupNumber)
  else:
    getAllCaseQuery = "SELECT %s FROM Case WHERE CaseNumber = '%s'" % (sf_fields, LookupNumber)
    
  print("Query : " + getAllCaseQuery)
  records = sf.query(query=getAllCaseQuery)
  count = len(records)

  if (count > 0):
      result['Id'] = records[0]['Id']
      result['CaseNumber'] = records[0]['CaseNumber']
      result['Type'] = records[0]['Type']
      result['Subtype'] = records[0]['Subtype__c']
      result['GSD_Language__c'] = records[0]['GSD_Language__c']
      result['Siebel_Order_Number__c'] = records[0]['Siebel_Order_Number__c']
      result['AccountType'] = records[0]['Account']['Sales_Program_Type__c']
      result['AccountNumber'] = records[0]['Account']['AccountNumber']
      result['GSD_Category__c'] = records[0]['Account']['GSD_Category__c']
      result['sf_count'] = 1
      print("return : " + json.dumps(result))
      return result
  print("return : ''")
  return ''
  
def unauthOrderLookup(sf, sf_fields, LookupNumber):
  result = {}
  print("--------------- UnauthOrderLookup -------------------------")
  
  getOrderHeaderQuery = "SELECT Case_Number__c, SIEBEL_Order_Number__c, Name FROM Order_Header__c  WHERE Siebel_Order_Number__c = '1-%s' " % (LookupNumber)
  print("orderHeaderQuery : " + getOrderHeaderQuery)
  records = sf.query(query=getOrderHeaderQuery)
  count = len(records)
  
  if (count > 0):
    LookupCaseNumber = records[0]['Case_Number__c']
    getAllCaseQuery = "SELECT %s FROM Case WHERE CaseNumber = '%s'" % (sf_fields, LookupCaseNumber)
    print("Query : " + getAllCaseQuery)
    records = sf.query(query=getAllCaseQuery)
    count = len(records)
  else:
    getAllCaseQuery = "SELECT %s FROM Case WHERE SIEBEL_Order_Number__c = '1-%s' ORDER BY Last_Modified_Date_Time__c DESC" % (sf_fields, LookupNumber)
    print("Query : " + getAllCaseQuery)
    records = sf.query(query=getAllCaseQuery)
    count = len(records)
    
  if (count > 0):
      result['Id'] = records[0]['Id']
      result['CaseNumber'] = records[0]['CaseNumber']
      result['Type'] = records[0]['Type']
      result['Subtype'] = records[0]['Subtype__c']
      result['GSD_Language__c'] = records[0]['GSD_Language__c']
      result['Siebel_Order_Number__c'] = records[0]['Siebel_Order_Number__c']
      result['AccountType'] = records[0]['Account']['Sales_Program_Type__c']
      result['AccountNumber'] = records[0]['Account']['AccountNumber']
      result['GSD_Category__c'] = records[0]['Account']['GSD_Category__c']
      result['sf_count'] = 1
      print("return : " + json.dumps(result))
      return result
  print("return : ''")
  return ''