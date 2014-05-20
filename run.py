# -*- coding: utf-8 -*-

import trello, requests, yaml, sys, time, shlex

from twisted.internet import reactor, task, defer, protocol
from twisted.python import log
from twisted.words.protocols import irc
from twisted.application import internet, service

colors = {"white": "\x030", "black": "\x031", "navy": "\x032", "green": "\x033",
          "red": "\x034", "darkred": "\x035", "purple": "\x036", "gold": "\x037",
          "yellow": "\x038", "lime": "\x039", "cyan": "\x0310", "lightcyan": "\x0311",
          "blue": "\x0312", "pink": "\x0313", "grey": "\x0314", "lightgrey": "\x0315",
          "bold": "\x02", "reset": "\x0f"}

with open('config.yml') as f:
    config = yaml.load(f.read())
HOST, PORT = config['host'], config['port']

# Utils
def get_tc(write=False): # tc = trello client
    return trello.TrelloClient(config["trello_key"], token=config["trello_token_" + ("write" if write else "read")])

def say(info, msg):
    info["msg"](info["channel"], msg)
    log.msg("{}: {}".format(info["channel"], msg))

def load_config():
    with open("config.yml") as f:
        config = yaml.load(f.read())

def save_config():
    with open("config.yml", "w") as f:
        f.write(yaml.dump(config))

def admin_check(info):
    if not info["nick"] in config["admins"]:
        say(info, "You can't use this command.")
        log.msg("{} was prevented from using {}".format(info["nick"], info["message"]))
        return False
    return True

def col(text, color):
    if color in colors:
        return colors[color] + text + colors["reset"]
    log.msg("col() : " + str(color) + " isn't a valid color")

def nicklookup(ircnick):
    return config["nickmap"][ircnick.lower()] if ircnick.lower() in config["nickmap"] else ircnick

def trellonicklookup(username):
    inverse = {v:k for k,v in config["nickmap"].iteritems()}
    return inverse[username.lower()] if username.lower() in inverse else username

# Commands
def u_addadmin(info, msg):
    """**!addadmin <nick> - Adds nick to list of users allowed to use commands other than listing cards and lists"""
    if not admin_check(info):
        return
    if not msg:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    if not msg in config["admins"]:
        config["admins"].append(msg)
        save_config()
        say(info, "Added {} to admin list.".format(col(msg, "lime")))
    else:
        say(info, "{} is already in admin list".format(col(msg, "lime")))

def u_deladmin(info, msg):
    """**!deladmin <nick> - Removes nick from list of users allowed to use commands other than listing cards and lists"""
    if not admin_check(info):
        return
    if not msg:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    if msg in config["admins"]:
        say(info, "Removed {} from admin list.".format(col(config["admins"].pop(config["admins"].index(msg)), "lime")))
        save_config()
    else:
        say(info, "{} is not in the admin list.".format(col(msg, "lime")))

def u_trellohelp(info, msg):
    """!trellohelp - List commands"""
    info["channel"] = info["nick"]
    for f in globals():
        if f[:2] == "u_":
            doc = globals()[f].__doc__
            if doc[:2] == "**":
                if not admin_check(info):
                    pass
                doc = doc[2:]
            say(info, doc)

def u_cards(info, msg):
    """!cards - List cards"""
    board = get_tc().get_board(config["board"])
    out = []
    for list in board.all_lists():
        lcards = []
        x = 1
        for a in list.list_cards():
            lcards.append(col(" " + str(x), "gold") + ":" + a.name.split(",")[0].replace("https://gist.github.com", "gist"))
            x += 1
        cards = "".join(lcards)
        outp = "{}:{}".format(col(list.name, "cyan"), cards)
        if " ".join(msg).lower() == list.name.lower():
            say(info,outp)
            return
        else:
            out.append(outp)
    if msg:
        say(info, "Couldn't find a list matching " + col(" ".join(msg), "cyan"))
        return
    for a in out:
        say(info,a)

def u_list(info, msg):
    """!list - List all cards"""
    u_cards(info, msg)

def u_pcards(info, msg):
    """!pcards <username> - List all cards assigned to username"""
    board = get_tc().get_board(config["board"])
    if not msg:
        msg = [info["nick"]]
    try:
        member = board.client.get_member(nicklookup(msg[0]))
    except trello.ResourceUnavailable:
        say(info, "Couldn't find member by searching for %s, please check you're using the correct username" % col(msg[0], "lime"))
        return    
    out = []
    for list in board.all_lists():
        lcards = []
        x = 1
        for a in list.list_cards():
            if member.id in a.member_ids:
                lcards.append(col(" " + str(x), "gold") + ":" + a.name.replace("https://gist.github.com", "gist"))
            x += 1
        cards = col("", "bold").join(lcards)
        outp = "{}:{}".format(col(list.name, "cyan"), cards)
        if lcards:
            out.append(outp)
    if not out:
        say(info, "No cards assigned to " + msg[0])
        return
    for a in out:
        say(info,a)

def u_ucards(info, msg):
    """!ucards <username> - Alias of !pcards"""
    u_pcards(info, msg)

def u_addcard(info, msg):
    """**!addcard <list> <card> [desc] - Adds card to specified list"""
    if not admin_check(info):
        return
    if not msg or not len(msg) in [2,3]:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    for list in board.all_lists():
        if msg[0].lower() in list.name.lower():
            card = list.add_card(msg[1], desc=msg[2] if len(msg) == 3 else None)
            say(info, "Card added.")

def u_getcard(info, msg):
    """!getcard <list> <number> - Get card info"""
    if not msg or len(msg) != 2:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc().get_board(config["board"])
    _card = None
    try:
        list = [list for list in board.all_lists() if list.name == msg[0]][0]
    except IndexError:
        say(info, "Couldn't find that list. Please use !cards to see options.")
        return
    try:
        card = list.list_cards()[int(msg[1]) - 1]
    except ValueError:
        say(info, col(msg[1], "gold") + " isn't an integer. Please provide an integer.")
        return
    except IndexError:
        say(info, "Couldn't find card number %s in list %s. Use !cards to see options." % (col(msg[1], "gold"), col(list.name, "cyan")))
        return
    say(info, "{} ({}) | Assigned: {}".format(card.name, card.description if card.description else "No description",
                                              ", ".join([col(board.client.get_member(id).username, "lime") for id in card.member_ids])))

def u_lists(info, msg):
    """!lists - Show lists"""
    board = get_tc().get_board(config["board"])
    say(info, ", ".join([col(list.name, "cyan") for list in board.all_lists()]))

def u_assign(info, msg):
    """**!assign <list> <number> <user> - Assign specified card to specified user"""
    if not admin_check(info):
        return
    if not msg or len(msg) != 3:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    try:
        list = [list for list in board.all_lists() if list.name == msg[0]][0]
    except IndexError:
        say(info, "Couldn't find that list. Please use !cards to see options.")
        return
    try:
        card = list.list_cards()[int(msg[1]) - 1]
    except ValueError:
        say(info, col(msg[1], "gold") + " isn't an integer. Please provide an integer.")
        return
    except IndexError:
        say(info, "Couldn't find card number %s in list %s. Use !cards to see options." % (col(msg[1], "gold"), col(list.name, "cyan")))
        return
    try:
        member = board.client.get_member(nicklookup(msg[2]))
    except trello.ResourceUnavailable:
        say(info, "Couldn't find member by searching for %s, please check you're using the correct username" % col(msg[2], "lime"))
        return
    try:
        card.assign(member.id)
        say(info, "%s successfully added to %s" % (col(nicklookup(msg[2]), "lime"), str(card.name)))
    except trello.ResourceUnavailable:
        log.err()
        say(info, "Something went wrong. Check list name, card name and member name to make sure they're all correct.")
    except (IndexError, KeyError):
        say(info, "Invalid response. The card may have still been added to the specified member.")

def u_unassign(info, msg):
    """**!unassign <list> <number> <user> - Unassign specified card from specified user"""
    if not admin_check(info):
        return
    if not msg or len(msg) != 3:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    try:
        list = [list for list in board.all_lists() if list.name == msg[0]][0]
    except IndexError:
        say(info, "Couldn't find that list. Please use !cards to see options.")
        return
    try:
        card = list.list_cards()[int(msg[1]) - 1]
    except ValueError:
        say(info, col(msg[1], "gold") + " isn't an integer. Please provide an integer.")
        return
    except IndexError:
        say(info, "Couldn't find card number %s in list %s. Use !cards to see options." % (col(msg[1], "gold"), col(list.name, "cyan")))
        return
    try:
        member = board.client.get_member(nicklookup(msg[2]))
    except trello.ResourceUnavailable:
        say(info, "Couldn't find member by searching for %s, please check you're using the correct username" % col(msg[2], "lime"))
        return
    try:
        board.client.fetch_json("/cards/{}/idMembers/{}".format(card.id, member.id), http_method='DELETE', post_args={'idMember': member.id})
        say(info, "%s successfully removed from card %s" % (col(nicklookup(msg[2]), "lime"), col(card.name, "gold")))
    except trello.ResourceUnavailable:
        say(info, "Unable to remove %s from %s. Is that user assigned to that card?" % (col(nicklookup(msg[2]), "lime"), col(card.name, "gold")))

def u_archive(info, msg):
    """**!archive <list> <number> - Remove card from specified list (close)"""
    if not admin_check(info):
        return
    if not msg or len(msg) != 2:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    try:
        list = [list for list in board.all_lists() if list.name == msg[0]][0]
    except IndexError:
        say(info, "Couldn't find that list. Please use !cards to see options.")
        return
    try:
        card = list.list_cards()[int(msg[1]) - 1]
    except ValueError:
        say(info, col(msg[1], "gold") + " isn't an integer. Please provide an integer.")
        return
    except IndexError:
        say(info, "Couldn't find card number %s in list %s. Use !cards to see options." % (col(msg[1], "gold"), col(list.name, "cyan")))
        return
    card.set_closed(True)
    say(info, "Card closed.")

def u_adduser(info, msg):
    """**!adduser <username> - Adds user to board. Email, username or ID allowed"""
    if not admin_check(info):
        return
    if not msg or len(msg) != 1:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    try:
        member = board.client.get_member(nicklookup(msg[0]))
    except trello.ResourceUnavailable:
        say(info, "Couldn't find member by searching for %s, please check you're using the correct username" % col(msg[2], "lime"))
        return
    try:
        board.client.fetch_json("/boards/{}/members/{}".format(board.id, member.id), http_method='PUT', post_args={'idMember': member.id, 'type': 'normal'})
        say(info, "%s added to board. Welcome!" % col(nicklookup(msg[0]), "lime"))
    except trello.ResourceUnavailable:
        log.err()
        say(info, "Unable to add %s to board." % col(nicklookup(msg[0]), "lime"))

def u_deluser(info, msg):
    """**!deluser <username> - Removes user from board. Email, username or ID allowed"""
    if not admin_check(info):
        return
    if not msg or len(msg) != 1:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    try:
        member = board.client.get_member(nicklookup(msg[0]))
    except trello.ResourceUnavailable:
        say(info, "Couldn't find member by searching for %s, please check you're using the correct username" % col(msg[2], "lime"))
        return
    try:
        board.client.fetch_json("/boards/{}/members/{}".format(board.id, member.id), http_method='DELETE', post_args={'idMember': member.id})
        say(info, "%s removed from board. Goodbye!" % col(nicklookup(msg[0]), "lime"))
    except trello.ResourceUnavailable:
        log.err()
        say(info, "Unable to remove %s from board." % col(nicklookup(msg[0]), "lime"))

def u_welcome(info, msg):
    """**!welcome <username> [ircnick] - Add user to organization. Email, username or ID allowed"""
    if not admin_check(info):
        return
    if not msg or not len(msg) in [1,2]:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    try:
        member = board.client.get_member(msg[0])
    except trello.ResourceUnavailable:
        say(info, "Couldn't find member by searching for %s, please check you're using the correct username" % col(msg[2], "lime"))
        return
    try:
        board.client.fetch_json("/organizations/{}/members/{}".format(config["orgname"], member.id), http_method='PUT', post_args={'idMember': member.id, 'type': 'normal'})
        say(info, "%s added to Trello organization. Welcome!" % col(member.username, "lime"))
    except trello.ResourceUnavailable:
        log.err()
        say(info, "Unable to add %s to organization." % col(member.username, "lime"))
    if len(msg) == 2:
        config["nickmap"][msg[1]] = msg[0]
        save_config()

def u_goodbye(info, msg):
    """**!goodbye <username> - Remove user from organization. Email, username or ID allowed"""
    if not admin_check(info):
        return
    if not msg or len(msg) != 1:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    try:
        member = board.client.get_member(nicklookup(msg[0]))
    except trello.ResourceUnavailable:
        say(info, "Couldn't find member by searching for %s, please check you're using the correct username" % col(msg[2], "lime"))
        return
    try:
        board.client.fetch_json("/organizations/{}/members/{}".format(config["orgname"], member.id), http_method='DELETE', post_args={'idMember': member.id})
        say(info, "%s removed from Trello organization. Goodbye!" % col(nicklookup(msg[0]), "lime"))
    except trello.ResourceUnavailable:
        log.err()
        say(info, "Unable to remove %s from organization." % col(nicklookup(msg[0]), "lime"))

def u_move(info, msg):
    """**!move <list> <number> <newlist> - Move card from one list to another"""
    if not admin_check(info):
        return
    if not msg or len(msg) != 3:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    try:
        list = [list for list in board.all_lists() if list.name == msg[0]][0]
    except IndexError:
        say(info, "Couldn't find list by %s. Please use !lists to see options." % msg[0])
        return
    try:
        card = list.list_cards()[int(msg[1]) - 1]
    except ValueError:
        say(info, col(msg[1], "gold") + " isn't an integer. Please provide an integer.")
        return
    except IndexError:
        say(info, "Couldn't find card number %s in list %s. Use !cards to see options." % (col(msg[1], "gold"), col(list.name, "cyan")))
        return
    try:
        newlist = [newlist for newlist in board.all_lists() if newlist.name == msg[2]][0]
    except IndexError:
        say(info, "Couldn't find list by %s. Please use !lists to see options." % msg[0])
        return
    try:
        card.change_list(newlist.id)
        say(info, "%s moved to %s" % (str(card.name), str(newlist.name)))
    except trello.ResourceUnavailable:
        log.err()
        say(info, "Unable to move %s to %s.")

def u_comment(info, msg):
    """**!comment <list> <number> <comment> - Comment on card. All comments come from the Willie user, but your nickname will be prepended. Comments don't need to be in quotes."""
    if not admin_check(info):
        return
    if not msg or len(msg) < 3:
        say(info, globals()[sys._getframe().f_code.co_name].__doc__)
        return
    board = get_tc(write=True).get_board(config["board"])
    try:
        list = [list for list in board.all_lists() if list.name == msg[0]][0]
    except IndexError:
        say(info, "Couldn't find list by %s. Please use !lists to see options." % msg[0])
        return
    try:
        card = list.list_cards()[int(msg[1]) - 1]
    except ValueError:
        say(info, col(msg[1], "gold") + " isn't an integer. Please provide an integer.")
        return
    except IndexError:
        say(info, "Couldn't find card number %s in list %s. Use !cards to see options." % (col(msg[1], "gold"), col(list.name, "cyan")))
        return
    try:
        card.comment(info["nick"] + ": " + " ".join(msg[2:]))
        say(info, "Comment added.")
    except trello.ResourceUnavailable:
        say(info, "Unable to add comment.")

class TrelloProtocol(irc.IRCClient):
    nickname = config['nick']
    password = config['password']
    username = config['nick']
    versionName = "Trello"
    versionNum = "v0.0.1"
    realname = config['nick']

    def signedOn(self):
        for channel in self.factory.channels:
            self.join(channel)

    def privmsg(self, user, channel, message):
        nick, _, host = user.partition('!')
        if not channel in self.factory.channels:
            return
#        log.msg("{} <{}> {}".format(channel, nick, message))
        if message[0][0] == "!":
            message = shlex.split(message.strip())
            msginfo = {'nick': nick, 'host': host, 'channel': channel, 'message': message, 'notice': self.notice, 'msg': self.msg}
            if channel == self.nickname:
                channel = nick
            try:
                log.msg("{} used {}".format(nick, " ".join(message)))
                globals()["u_" + message[0][1:]](msginfo, message[1:] if len(message) > 1 else [])
            except KeyError:
                log.msg("Command not found, probably for another bot")

class TrelloFactory(protocol.ReconnectingClientFactory):
    protocol = TrelloProtocol
    channels = config["channels"]

if __name__ == '__main__':
    reactor.connectTCP(HOST, PORT, TrelloFactory())
    log.startLogging(sys.stdout)
    reactor.run()

elif __name__ == '__builtin__':
    application = service.Application('Trello')
    ircService = internet.TCPClient(HOST, PORT, TrelloFactory())
    ircService.setServiceParent(application)

