#!/usr/bin/python3.6

'''******************************************************************************
|   FileName: GenerateAccessToken.py						                    |
|   Description: This script will fetch Access Tokens from Keycloak server 	    |
|		 which are used in client registration.			                        |
|   Umesh 16-Jul-18								                                |
******************************************************************************'''
'''******************************************************************************
|   Python 3.6 Modules Used							                            |
|   paramiko : To SSH, execute sql query and bring sql results to local machine	|
|   secrets  : To generate random hexadecimal auth key			        |
|   requests : To POST http request						                        |
******************************************************************************'''

import sys
import secrets
from paramiko import client
import re, time, os, csv
import httpRequest


class ssh:
    client = None
    OrigFile = None
    TermFile = None
    OrigPassFile = None
    TermPaddFile = None
    def __init__(self, address, username, password,condition):
        if os.path.exists('accesstoken_O.csv'):
            os.remove('accesstoken_O.csv')
        if os.path.exists('accesstoken_T.csv'):
            os.remove('accesstoken_T.csv')
        self.OrigFile = open("accesstoken_O.csv",'a')
        self.OrigFile.write('SEQUENTIAL \n')
        self.TermFile = open("accesstoken_T.csv",'a')
        self.TermFile.write('SEQUENTIAL \n')
        if condition == 'T':
            print("Connecting to server...")
            self.client = client.SSHClient()
            self.client.set_missing_host_key_policy(client.AutoAddPolicy())
            self.client.connect(address, username=username, password=password, look_for_keys=False)

    def __del_(self):
        self.OrigFile.close()
        self.TermFile.close()
        self.client.close()
        self.TermPassFile.close()

    def sendCommand(self, command):
       if(self.client):
       #   print(command)
          stdin, stdout, stderr = self.client.exec_command(command)
          alldata = stdout.channel.recv(1024)
          return alldata
       else:
          print("Unable SSH to XDM.....");

    def prepareSqlStatement(self,mdn,ip,pttid):
       actKey = ' /opt/TimesTen/kodiak/bin/ttIsqlCS -connStr \"TTC_SERVER='+ip+';TCP_Port=53389;TTC_SERVER_DSN=DG_'+pttid+'_6;UID=kodiakdb;PWD=kodiak\" -v 1 -e \" select SUBSCRIPTIONKEY from DG.TMPVASSUBSCRIPTIONKEYINFO where mdn=' +str(mdn)+ ";quit;\"" 
       return actKey

    def prepareSqlStatement1(self,mdn,ip,pttid,md5=None):
        if md5 == None:
            md5Pass = ' /opt/TimesTen/kodiak/bin/ttIsqlCS -connStr \"TTC_SERVER='+ip+';TCP_Port=53389;TTC_SERVER_DSN=DG_'+pttid+'_6;UID=kodiakdb;PWD=kodiak\" -v 1 -e \" select CLIENT_PASSWORD from DG.POCSUBSCRINFO where mdn='+mdn+';quit;\"'
           # print(md5Pass)
            return md5Pass
        elif md5:
            updateDB = '/opt/TimesTen/kodiak/bin/ttIsqlCS -connStr \"TTC_SERVER='+ip+';TCP_Port=53389;TTC_SERVER_DSN=DG_'+pttid+'_6;UID=kodiakdb;PWD=kodiak\" -v 1 -e \" update DG.DEVICE_INFO set DEVICEDIGESTPASSWD=\''+md5[1:33]+'\' where DEVICEID='+mdn+';quit; \"'
            #print(updateDB)
            return updateDB

    def sendActivationRequest(self,actKey,authKey,actServerIpAddress):
        self.password = httpRequest.postActivationRequest(actKey,authKey,actServerIpAddress);
        #print(self.password)
        return self.password

    def writeTokenInFile(self,mdn,token,action,ssrc):
        if action == 'O':
            self.OrigFile.write('+')
            self.OrigFile.write(mdn)
            self.OrigFile.write(";")
            self.OrigFile.write(str(ssrc))
            self.OrigFile.write(";")
            self.OrigFile.write(token)
            self.OrigFile.write(";\n")
        elif action == 'T':
            self.TermFile.write('+')
            self.TermFile.write(mdn)
            self.TermFile.write(";")
            self.TermFile.write(str(ssrc))
            self.TermFile.write(";")
            self.TermFile.write(token)
            self.TermFile.write(";\n")

    def writePasswordToFile(self,mdn,password,act):
        #print(mdn,password)
        if act == 'O':
            self.OrigPassFile.write(mdn)
            self.OrigPassFile.write(";")
            self.OrigPassFile.write(password)
            self.OrigPassFile.write(";\n")
        elif act == 'T':
            self.TermPassFile.write(mdn)
            self.TermPassFile.write(";")
            self.TermPassFile.write(password)
            self.TermPassFile.write(";\n")
        


if __name__ == '__main__':
    
    startOrigMDN = os.environ['SUBSCRIBER_START_SEQUENCE'];
    startTermMDN = os.environ['TERM_SUBSCRIBER_START_SEQUENCE']
    totalOrigSession = os.environ['TOTAL_PREESTABLISHED_SESSION']
    totalTermSession = os.environ['TOTAL_TERM_PREESTABLISHED_SESSION']
    xdmIpAddress = os.environ['XDM_SERVER_IP']
    actServerIpAddress = os.environ['ACTIVATION_SERVER_IP']
    keycloakIpAddress = os.environ['KEYCLOAK_SERVER_IP']
    pttid = os.environ['XDM_PTTSERVERID']
    origSSRC = 1111111110
    termSSRC = 2222222220

    print("\n\n\t\tTo Start from Client Activation ENTER: 1\n\t\tTo Generate Only Access Token ENTER:   2\n")
    opt = input("Enter Your Choice:")
#    option = input("Enter y/Y if you want generate activation keys in script itself OR \nEnter n/N if you want to take activation keys from DB:")

    if opt == '1':
        option = input("Enter y/Y if you want generate activation keys in script itself(will use last 7 digits of MDN) OR \nEnter n/N if you want to take activation keys from DB:")
        print("Activating Clients please wait...")
        accessToken = ssh(xdmIpAddress,'kodiak','kodiak','T');

        if os.path.exists('password_O.csv'):
            os.remove('password_O.csv')

        if os.path.exists('password_T.csv'):
            os.remove('password_T.csv')

        accessToken.OrigPassFile = open('password_O.csv','a')
        accessToken.TermPassFile = open('password_T.csv','a')

        tmpMDN = int(startOrigMDN)

        for i in range(1,int(totalOrigSession)+1):
            
            if i != 1:
                tmpMDN = tmpMDN + 1
            #origSSRC = origSSRC + 1

            print(tmpMDN)
            
            if option == 'n' or option == 'N':	
                sqlst=""
                sqlst = accessToken.prepareSqlStatement(str(tmpMDN),xdmIpAddress,pttid)
                tmpActKey = accessToken.sendCommand(sqlst)
        
                if tmpActKey == b'':
                    print("Activation Key not found for MDN:{}".format(tmpMDN))
                    continue
                actKey = re.findall(r'-?\d+\.?\d*',str(tmpActKey))
                authKey = secrets.token_hex(16)
                password = accessToken.sendActivationRequest(actKey[0],authKey,actServerIpAddress)
                if password == "ERROR":
                    print("ERROR: Invalid Activation key MDN:{}".format(tmpMDN))
                    continue
                
            elif option == 'y' or option == 'Y':
                md = str(tmpMDN)
                actKey = md[5:]
                print(actKey)
                authKey = secrets.token_hex(16)
      
                password = accessToken.sendActivationRequest(actKey,authKey,actServerIpAddress)
                if password == "ERROR":
                    print("ERROR: Invalid Activation key MDN:{}".format(tmpMDN))
                    continue
            
            accessToken.writePasswordToFile(str(tmpMDN),password,'O')

            sqlSt1 = accessToken.prepareSqlStatement1(str(tmpMDN),xdmIpAddress,pttid)
            md5Pass = accessToken.sendCommand(sqlSt1)
            #print(md5Pass)
            md5Pass1=re.findall(r'<(.*)>',(str(md5Pass.decode("utf-8"))))
            updateMd5Pass = accessToken.prepareSqlStatement1(str(tmpMDN),xdmIpAddress,pttid,md5Pass1[0])
            accessToken.sendCommand(updateMd5Pass)
        

        tmpMDN = int(startTermMDN)
        for i in range(1,int(totalTermSession)+1):
   
            if i != 1:
                tmpMDN = tmpMDN + 1
            #termSSRC = termSSRC + 1
            print(tmpMDN)

            if option == 'n' or option == 'N':
                sqlst=""
                sqlst = accessToken.prepareSqlStatement(str(tmpMDN),xdmIpAddress,pttid)
                tmpActKey = accessToken.sendCommand(sqlst)
                if tmpActKey == b'':
                    print("Activation Key not found for MDN:{}".format(tmpMDN))
                    continue
                actKey = re.findall(r'-?\d+\.?\d*',str(tmpActKey))
     
                authKey = secrets.token_hex(16)
                password = accessToken.sendActivationRequest(actKey[0],authKey,actServerIpAddress)
                if password == "ERROR":
                    print("ERROR: Invalid activation key MDN:{}".format(tmpMDN))
                    continue

            if option == 'y' or option == 'Y':
                md = str(tmpMDN)
                actKey = md[5:]
                print(actKey)
                authKey = secrets.token_hex(16)

                password = accessToken.sendActivationRequest(actKey,authKey,actServerIpAddress)
                if password == "ERROR":
                    print("Activation Key not found for MDN:{}".format(tmpMDN))
                    continue

            accessToken.writePasswordToFile(str(tmpMDN),password,'T')

            sqlSt1 = accessToken.prepareSqlStatement1(str(tmpMDN),xdmIpAddress,pttid)
            md5Pass = accessToken.sendCommand(sqlSt1)
            #print(md5Pass)
            md5Pass1=re.findall(r'<(.*)>',(str(md5Pass.decode("utf-8"))))
            updateMd5Pass = accessToken.prepareSqlStatement1(str(tmpMDN),xdmIpAddress,pttid,md5Pass1[0])
            #print(updateMd5Pass)
            accessToken.sendCommand(updateMd5Pass)
    

            #token = httpRequest.postAccessTokenRequest(keycloakIpAddress,str(tmpMDN),str(password))
            #accessToken.writeTokenInFile(str(tmpMDN),token,'T',termSSRC)

            opt = '2'

    if opt == '2':
        accessToken = accessToken = ssh(xdmIpAddress,'kodiak','kodiak','F');
        try: 
            accessToken.OrigPassFile = open("password_O.csv")
            reader = csv.reader(accessToken.OrigPassFile, delimiter=';')
            for line in reader:
                token = httpRequest.postAccessTokenRequest(keycloakIpAddress,line[0],line[1])
                accessToken.writeTokenInFile(line[0],token,'O',termSSRC)
                origSSRC = origSSRC + 1
        except FileNotFoundError:
            print("password_O.csv File not Found, Please Activate Clients")

        try: 
            accessToken.TermPassFile = open("password_T.csv")
            reader = csv.reader(accessToken.TermPassFile, delimiter=';')
            for line in reader:
                token = httpRequest.postAccessTokenRequest(keycloakIpAddress,line[0],line[1])
                accessToken.writeTokenInFile(line[0],token,'T',termSSRC)
                termSSRC = termSSRC + 1
        except FileNotFoundError:
            print("password_T.csv File not Found, Please Activate Clients")
