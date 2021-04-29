import logging
import requests
import time
import re

logger = logging.getLogger(__name__.rsplit(".")[-1])


class Volkszahler:

    # Volkszahler EMS Module
    # Fetches Consumption and Generation details from Volkszahler API

    cacheTime = 10
    config = None
    configConfig = None
    configVolkszahler = None
    consumedW = 0
    fetchFailed = False
    generatedW = 0
    lastFetch = 0
    master = None
    serverIP = None
    serverPort = 80
    status = False
    timeout = 2
    uuid = None

    def __init__(self, master):
        self.master = master
        self.config = master.config
        self.configConfig = master.config.get("config", {})
        self.configVolkszahler = master.config["sources"].get("Volkszahler", {})
        self.serverIP = self.configVolkszahler.get("serverIP", None)
        self.serverPort = self.configVolkszahler.get("serverPort", 80)
        self.status = self.configVolkszahler.get("enabled", False)
        self.uuid = self.configVolkszahler.get("uuid", None)

        # Unload if this module is disabled or misconfigured
        if (not self.status) or (not self.serverIP) or (not self.uuid):
            self.master.releaseModule("lib.TWCManager.EMS", self.__class__.__name__)
            return None

    def getConsumption(self):

        if not self.status:
            logger.debug("EMS Module Disabled. Skipping getConsumption")
            return 0

        # While we don't have separate generation or consumption values, if
        # the value is a positive value we report it as consumption
        if self.generatedW < 0:
            return self.generatedW * -1
        else:
            return 0

    def getGeneration(self):

        if not self.status:
            logger.debug("EMS Module Disabled. Skipping getGeneration")
            return 0

        # Perform updates if necessary
        self.update()

        # Return generation value
        if self.generatedW > 0:
            return self.generatedW
        else:
            return 0

    def getGenerationValues(self):
        url = "http://" + self.serverIP + ":" + self.serverPort + "/api/data.txt?from=now&uuid=" + self.uuid
        headers = {"content-type": "text/plain"}

        # Update fetchFailed boolean to False before fetch attempt
        # This will change to true if the fetch failed, ensuring we don't then use the value to update our cache
        self.fetchFailed = False

        try:
            logger.debug("Fetching Volkszahler EMS sensor values")
            httpResponse = requests.get(url, headers=headers, timeout=self.timeout)
        except requests.exceptions.ConnectionError as e:
            logger.log(
                logging.INFO4, "Error connecting to Volkszahler to fetch sensor values"
            )
            logger.debug(str(e))
            self.fetchFailed = True
            return False
        except requests.exceptions.ReadTimeout as e:
            logger.log(
                logging.INFO4, "Read Timeout occurred fetching Volkszahler sensor values"
            )
            logger.debug(str(e))
            self.fetchFailed = True
            return False

        if httpResponse.status_code != 200:
            logger.log(
                logging.INFO4,
                "Volkszahler API reports HTTP Status Code " + str(httpResponse.status_code),
            )
            return False

        if not httpResponse:
            logger.log(logging.INFO4, "Empty HTTP Response from Volkszahler API")
            return False

        else:

            msgMatch = re.search("^(.+) W$", httpResponse.text, re.DOTALL)

            if msgMatch:
                self.generatedW = -float( msgMatch.group(1) )
            else:
                logger.log(logging.INFO4, "Did not find expected value inside of Volkszahler API response.")

    def setCacheTime(self, cacheTime):
        self.cacheTime = cacheTime

    def setTimeout(self, timeout):
        self.timeout = timeout

    def update(self):
        # Update function - determine if an update is required

        if (int(time.time()) - self.lastFetch) > self.cacheTime:
            # Cache has expired. Fetch values from Volkszahler.
            self.getGenerationValues()

            # Update last fetch time
            if self.fetchFailed is not True:
                self.lastFetch = int(time.time())

            return True
        else:
            # Cache time has not elapsed since last fetch, serve from cache.
            return False