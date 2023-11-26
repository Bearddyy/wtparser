import re
import sys
import os
import pandas as pd
from functools import cache

import timeit # for timing the code

# In the replay file the table starts with the following bytes
START_OF_TABLE = [0x01, 0x16, 0xC6, 0x01]
TABLE_HEADER_SIZE = 211 # The size of the header of the table in bytes
END_OF_PLAYERS_SECTION = [0x00, 0x00, 0x00, 0x00]
START_OF_SCORES_SECTION = [0x03, 0x00, 0x00, 0x01]

# Score table delimination
ROW_SIZE = 152
AIR_KILLS = 16
GROUND_KILLS = 24
ASSISTS = 72
DEATHS = 80 #83
CAPTURES = 88
SQUAD = 128
TEAM = 144
SCORE = [104,105]

PLAYER_ID_OFFSET = -1
VEHICLE_NAME_LENGTH = 6
VEHICLE_NAME_START = 7

def timeFunction(function, *args):
    start = timeit.default_timer()
    returns = function(*args)
    end = timeit.default_timer()
    print(f"Time Taken: {end - start:.10f}s")
    return returns

def timeStart():
    return timeit.default_timer()

def timeEnd(start):
    end = timeit.default_timer()
    print(f"Time Taken: {end - start:.10f}s")

def get_players(playersTable):
    # Each player has 2 or 3 sections (depending on if they have a clan tag), delimited by 0x00
    # Each player always has an ID so we need to split on that
    # b'Player Name' b'-CLAN TAG-' b'ID'
    # the ID is always just numbers
    
    # Split the table on \x00
    splitTable = playersTable.split(b'\x00')
    # reverse the list as its easier to split on the ID
    splitTable.reverse()

    players = dict()

    playerIndex = 0
    for i, entry in enumerate(splitTable):
        if entry.isdigit():
            # This is an ID
            ID = int(entry.decode("utf-8"))
            clanTag = None
            # if the 2nd next entry is not a digit then this player has a clan tag
            if not splitTable[i+2].isdigit():
                # The next entry is the clan tag
                clanTag = splitTable[i+1].decode("utf-8")
                # The next entry is the name
                name = splitTable[i+2].decode("utf-8")
            else:
                # The next entry is the name
                name = splitTable[i+1].decode("utf-8")
            # Add the player to the dict
            players[ID] = {"ID" :ID, "name":name, "clanTag":clanTag, "index":playerIndex}
            playerIndex += 1
    # because we reversed the list we need to reverse player indexs'
    for player in players.values():
        player["index"] = playerIndex - player["index"] - 1
    return players


def get_scores(scoresTable, players):
    # Split the table into rows of ROW_SIZE bytes
    splitTable = [scoresTable[i:i+ROW_SIZE] for i in range(0, len(scoresTable), ROW_SIZE)]

    # Remove rows that are not players
    splitTable = splitTable[:len(players)]

    # Each Row is a player
    for i,row in enumerate(splitTable):
        # find the player ID from the index
        for ID, player in players.items():
            if player["index"] == i:
                break
        players[ID]["airKills"] = int.from_bytes(row[AIR_KILLS:AIR_KILLS+4], byteorder="little")
        players[ID]["groundKills"] = int.from_bytes(row[GROUND_KILLS:GROUND_KILLS+4], byteorder="little")
        players[ID]["assists"] = row[ASSISTS]
        players[ID]["deaths"] = row[DEATHS]
        players[ID]["captures"] = row[CAPTURES]
        players[ID]["squad"] = row[SQUAD]
        players[ID]["team"] = row[TEAM]
        players[ID]["score"] = row[SCORE[0]] + row[SCORE[1]]*256
    return players

@cache
def lookup_nation(vehicleName):
    # for speed we first just check if the nation is present in the name
    nations = {
        "us_" : "USA",
        "ussr_" : "USSR",
        "germ_" : "Germany",
        "uk_" : "Great Britain",
        "jp_" : "Japan",
        "it_" : "Italy",
        "fr_" : "France",
        "cn_" : "China",
        "sw_" : "Sweden",
        "il_" : "Israel",
        }

    for nation in nations:
        if nation == vehicleName[:len(nation)]:
            return nations[nation]

    # if we couldn't find the nation in the name, we need to look it up

    # read in the lookup.txt
    with open("lookup.txt", "r", encoding="utf-8") as f:
        lookup = f.read()
    
    # find index of vehicle name
    vehicleNameIndex = lookup.find(vehicleName)

    # if the vehicle name is not found, return None
    if vehicleNameIndex == -1:
        return None
    
    # once the vehicle name is found, index back to the nation
    # nation is a like similar to "==== Great Britain ===="
    endOfNationIndex = lookup.rfind("====", 0, vehicleNameIndex)

    # nation is the string between the last ==== and the next ====
    startOfNationIndex = lookup.rfind("====", 0, endOfNationIndex-1) + 4
    nation = lookup[startOfNationIndex:endOfNationIndex-1]
    return nation


def get_vehicles(data):
    # search for occurences of the following bytes
    lookup = b'\x90..\x01\x20\x01'
    # find all occurences
    occurences = [m.start() for m in re.finditer(lookup, data)]
    # player ID is 4 bytes before the occurence
    playerIndex = [int(data[i+PLAYER_ID_OFFSET]) for i in occurences]
    # for some reason, the player Index is offset by the minumum number in the set
    playerIndex = [i-(min(playerIndex)) for i in playerIndex]

    vehicleNameLengths = [int(data[i+VEHICLE_NAME_LENGTH]) for i in occurences]
    vehicleNames = [data[i+VEHICLE_NAME_START:i+VEHICLE_NAME_START+length].decode("utf-8") for i,length in zip(occurences, vehicleNameLengths)]
    # print ID and vehicle name
    #for ID, name in zip(playerIDs, vehicleNames):
    #    print(f"{ID}\t{name}")
    
    # create a dict of player IDs and vehicle names
    playerVehicles = dict()
    for index, vehicleName in zip(playerIndex, vehicleNames):
        if index not in playerVehicles:
            playerVehicles[index] = set([vehicleName])
        else:
            playerVehicles[index].add(vehicleName)
    return playerVehicles
    
def parse_replay_data(data):
        
    # Find the start of the table
    startOfResultsTable = data.find(bytes(START_OF_TABLE))
    startOfResultsTable += len(START_OF_TABLE)
    
    resultsTable = data[startOfResultsTable:]
    
    # Find the end of the table
    endOfPlayersTable = resultsTable.find(bytes(END_OF_PLAYERS_SECTION))
    
    # Get the Players table
    playersTable = resultsTable[TABLE_HEADER_SIZE:endOfPlayersTable]

    players = get_players(playersTable)

    # Scores is from the players table to the START_OF_SCORES_SECTION
    scoresTable = resultsTable[endOfPlayersTable + len(END_OF_PLAYERS_SECTION):]
    startOfScoresTable = scoresTable.find(bytes(START_OF_SCORES_SECTION))
    scoresTable = scoresTable[startOfScoresTable + len(START_OF_SCORES_SECTION):]

    players = get_scores(scoresTable, players)

    # initialise vehicles
    for player in players.values():
        player["vehicles"] = []

    # parse vehicles
    vehiclesList = get_vehicles(data)
    for index, vehicles in vehiclesList.items():
        for ID, player in players.items():
            if player["index"] == index:
                break
        if 'dummy_plane' not in vehicles:
            players[ID]["vehicles"] = vehicles
            # get nation
            for vehicle in vehicles:
                nation = lookup_nation(vehicle)
                if nation is not None:
                    players[ID]["nation"] = nation
                    break
                else:
                    players[ID]["nation"] = None
    
    return players

def main():

    file = sys.argv[1]
    
    # expect a path to a folder, read all files in the folder and concat them
    
    start = timeStart()
    if os.path.isdir(file):
        data = b''
        for f in os.listdir(file):
            #only parse the files with an odd number
            # eg: 0007.wrpl
            if int(f.split(".")[0]) % 2 == 0:
                continue
            with open(os.path.join(file, f), "rb") as replay:
                data += replay.read()
    else:
        with open(file, "rb") as replay:
            data = replay.read()
    timeEnd(start)
    
    start = timeStart()
    players = parse_replay_data(data)
    timeEnd(start)


    for player in players.values():
        print(player["index"], end="\t")
        try:
            print(player["nation"], end="\t")
        except:
            print("Nation", end="\t")
        print(player["ID"], end="\t")
        try:
            print(player["name"], end="\t")
        except:
            print("Chinese Name", end="\t")
        print(f"{player['score']}, {player['airKills']}, {player['groundKills']}, {player['assists']}, {player['captures']}, {player['deaths']}, {player['vehicles']}")
  

if __name__ == "__main__":
    main()