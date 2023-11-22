import re
import sys
import os
import pandas as pd

# In the replay file the table starts with the following bytes
START_OF_TABLE = [0x01, 0x16, 0xC6, 0x01]
TABLE_HEADER_SIZE = 211 # The size of the header of the table in bytes
END_OF_PLAYERS_SECTION = [0x00, 0x00, 0x00, 0x00]
START_OF_SCORES_SECTION = [0x03, 0x00, 0x00, 0x01]

# Score table delimination
ROW_SIZE = 152
AIR_KILLS = 20
GROUND_KILLS = 28
ASSISTS = 76
DEATHS = 84
CAPTURES = 92
SQUAD = 132
TEAM = 148
SCORE = [108,109]

def getPlayers(playersTable):
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
            # if the 2nd next entry is not a digit then this player has a clan tag
            if not splitTable[i+2].isdigit():
                # The next entry is the clan tag
                clanTag = splitTable[i+1].decode("utf-8")
                # The next entry is the name
                name = splitTable[i+2].decode("utf-8")
            else:
                # The next entry is the name
                name = splitTable[i+1].decode("utf-8")
                clanTag = None
            # Add the player to the dict
            players[playerIndex] = [ID, name, clanTag]
            playerIndex += 1

    return players


def getScores(scoresTable, players):
    # Split the table into rows of ROW_SIZE bytes
    splitTable = [scoresTable[i:i+ROW_SIZE] for i in range(0, len(scoresTable), ROW_SIZE)]

    # Remove rows that are not players
    splitTable = splitTable[:len(players)]
    for row in splitTable:
        for val in row:
            print(val, end=" ")
        print()

    # Each Row is a player
    for row, playerIndex in zip(splitTable, players.keys()):
        # Print player and ground kills
        print(f"{players[playerIndex][1]}: {row[GROUND_KILLS]} ground kills")
        

def parseReplay(filename):
    # Open the file
    with open(filename, "rb") as f:
        # Read the file as bytes
        data = f.read()
    
    # Find the start of the table
    startOfResultsTable = data.find(bytes(START_OF_TABLE))
    startOfResultsTable += len(START_OF_TABLE)

    resultsTable = data[startOfResultsTable:]
    
    # Find the end of the table
    endOfPlayersTable = resultsTable.find(bytes(END_OF_PLAYERS_SECTION))
    
    # Get the Players table
    playersTable = resultsTable[TABLE_HEADER_SIZE:endOfPlayersTable]

    players = getPlayers(playersTable)

    # Scores is from the players table to the START_OF_SCORES_SECTION
    scoresTable = resultsTable[endOfPlayersTable + len(END_OF_PLAYERS_SECTION):]
    startOfScoresTable = scoresTable.find(bytes(START_OF_SCORES_SECTION))
    scoresTable = scoresTable[startOfScoresTable + len(START_OF_SCORES_SECTION):]

    scores = getScores(scoresTable, players)


def main():
    file = sys.argv[1]
    parseReplay(file)


if __name__ == "__main__":
    main()