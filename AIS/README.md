# Code to suck in AIS payloads embeded in NEMA sentences from either UDP datagrams or a serial feed.

`receiver.py` is the main program which does the following:
- Store the datagrams into a database
- Decode NEMA sentences and build AIS payloads
- Decrypt the AIS payloads
- Store the AIS contents in a database
- Save some of the AIS contents into a CSV file
- Build up the AIS contents from historical AIS contents for each MMSI
- Send a JSON datagram to requested UDP listeners

`replay.py` reads in a database and sends out datagrams or serial lines for testing `receiver.py`

`udpClient.py` is a sample UDP listener for the JSON messages

`AIS.service` is the systemctl service for executing `receiver.py`

`sample.raw.db` is a set of 10,000 AIS messages from a cruise in 2021 in the Gulf of Mexico

`sample.json.gz` is a sample of the JSON AIS messages received by `udpClient.py`
