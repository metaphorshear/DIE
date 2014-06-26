from twisted.protocols.basic import LineOnlyReceiver
from twisted.internet.protocol import ServerFactory
from twisted.internet import reactor, defer
from twisted.python import log
from random import getrandbits


class Channel(object):
   def __init__(self, name, creator, topic=""):
      self.name = name
      self.topic = topic
      self.users = []
      self.ops = [creator]
      self.private = False
      self.token = ""
      
   def join(self, user):
      if user in self.users:
         return True
      if self.token != "":
         if self.name not in user.tokens or user.tokens[self.name] != self.token:
            user.write("This room is protected, and you lack the necessary authentication token.")
            return False
      self.users.append(user)
      if self.topic != "":
         user.write("Welcome to {0}. Today's topic: ".format(self.name)+self.topic)
      return True
   
   def part(self, user, message):
      self.write('User {0} has left ("{1}")'.format(user.name, message))
      self.users.remove(user)
      
   def chat(self, user, message):
      self.write('{0}: {1}'.format(user.name, message))
             
   def write(self, message):
      for other in self.users:
         if other.current == self:
            other.write(message)

      
class User(object):
   def __init__(self, name, con):
      self.name = name
      self.con = con
      self.channels = [None]
      self.current = None
      self.tokens = {}
      
   def write(self, message): #deferred candidate?
      self.con.sendLine(message)
   
class Command(object):
   """This class is used to execute commands, i.e., any line received from the client beginning with "/" will be handled here.
      Initially, I handled commands directly in ChatProtocol. However, there are as many instances of ChatProtocol as there are
      users connected to the server, so that seemed a bit unwise. Likewise, many member functions originally part of User
      have been moved here, though they may have conceptually fit better there, as there will be only one instance of Command,
      it should save a lot of memory. The tradeoff is that each member function must take a user to operate on, and
      the available channels are accessed via the user's con member, which is a ChatProtocol object."""
      
   @staticmethod
   def list_commands(user):
      user.write(" ".join(user.con.commands).upper())
   
   @staticmethod
   def help_command(user, cmd):
      if cmd.lower() not in user.con.commands:
         return user.con.handle_COMMAND('commands')
      user.write(cmd)
      user.write(user.con.commands[cmd][1])
   
   @staticmethod
   def list_rooms(user):
      if len(user.con.channels) == 0 or len(user.con.channels) <= user.con.private[0]:
         user.write("No active rooms.")
         return
      user.write("Active rooms are:")
      for room in user.con.channels:
         if user.con.channels[room].private == True:
            continue
         else:
            user.write("* {0} ({1})".format(room, len(user.con.channels[room].users)))
      user.write("end of list.")
      
   @staticmethod
   def msg(me, you, message):
      if you not in me.con.users:
         me.write("No such person.")
      else:
         you = me.con.users[you]
         you.write('{0} says, "{1}"'.format(me.name, message))
      
   @staticmethod   
   def disconnect(user, message):
      room = user.channels.pop()
      while room is not None:
         room.part(user, message)
         room = user.channels.pop()
      user.write("BYE")
      user.con.transport.loseConnection()
      
   @staticmethod
   def join(user, channel, topic=""):
      if channel not in user.con.channels: #if channel does not exist on the server
         user.con.channels[channel] = Channel(channel, user, topic)
      user.write("entering room: {0}".format(channel))
      channel = user.con.channels[channel]
      if channel.join(user) == True:
         user.channels.append(channel)
         user.current = channel
         for other in channel.users:
            st = "* "+other.name
            if user == other:
               st+=" (** this is you)"
            user.write(st)
         user.write("end of list")
      else:
         user.write("Failed to enter {0}".format(channel.name))
         
   @staticmethod
   def part(user, message):
      if user.current is not None:
         user.current.part(user, message)
         user.channels.remove(user.current)
         user.current = user.channels[-1]
      else:
         user.write("You are not in a room.")
      
   @staticmethod
   def switch(user, channel):
      if channel in user.con.channels:
         if channel in user.channels:
            user.current = channel
            return
      user.con.handle_COMMAND('join {0}'.format(channel))
         
   @staticmethod
   def topic(user, topic):
      if user.current is None: return
      if user in user.current.ops:
         user.current.topic = topic
         user.write("Topic set.")
         
   @staticmethod
   def toggleprivate(user, channel=""):
      if channel=="":
         channel = user.current #I know, I know. Violates DRY. But I'm not sure how to fix it
         if channel is None: return
      else:
         try: channel = user.con.channels[channel]
         except LookupError: return
      if user in channel.ops:
         if channel.private == False:
            channel.private = True
            user.write("{0} is now private.".format(channel.name))
            user.con.private[0] += 1
         else:
            channel.private = False
            user.write("{0} is no longer private.".format(channel.name))
            user.con.private[0] -= 1
         
   @staticmethod
   def toggleop(user, other, channel=""):
      if other not in user.con.users:
         return user.write("No such person.")
      else:
         other = user.con.users[other]
      if user == other: #avoid some weird situations
         return
      if channel=="" and user.current is not None: channel = user.current
      elif channel == "" and user.current is None:
         user.write("Join a channel first.")
         return
      else:
         try: channel = user.con.channels[channel]
         except LookupError: return
      if user in channel.ops:
         if other not in channel.ops:
            channel.ops.append(other)
            user.write("Op status granted for "+other.name)
            other.write("You have been given op status for "+channel.name)
         else:
            channel.ops.remove(other)
            user.write("Op status removed from "+other.name)
            other.write("Your op status for {0} has been revoked.".format(channel.name))
         
   @staticmethod
   def invite(user, other, channel=""):
      if other not in user.con.users:
         return user.write("No such person.")
      else:
         other = user.con.users[other]
      if channel == "" and user.current is not None: channel = user.current
      elif channel == "" and user.current is None: return
      else:
         try: channel = user.con.channels[channel]
         except LookupError: return
      if channel.private and user not in channel.ops:
         return user.write("You aren't qualified to do that. Ask an op to invite your little friend.")
      other.write("{0} has invited you to join {1}. If you want to accept, type '/join {1}'".format(user.name, channel.name))
      other.tokens[channel.name]=channel.token
      
   @staticmethod
   def protect(user, channel=""):
      if channel == "" and user.current is not None: channel = user.current
      elif channel == "" and user.current is None: return
      else:
         try: channel = user.con.channels[channel]
         except LookupError: return
      if user in channel.ops:
         channel.token=getrandbits(128) #pointless to use real security, since the server doesn't use SSL and all data is in the clear
         for p in channel.ops:
            p.tokens[channel.name]=channel.token
         user.write("Okay, {0} is now protected.".format(channel.name))
            
   @staticmethod
   def unprotect(user, channel=""):
      if channel == "" and user.current is not None: channel = user.current
      elif channel == "" and user.current is None: return
      else:
         try: channel = user.con.channels[channel]
         except LookupError: return
      if user in channel.ops:
         channel.token = ""
         user.write("Removed protection from {0}".format(channel.name))
            



class ChatProtocol(LineOnlyReceiver):
   
   def __init__(self, users, channels, private):
      self.users = users
      self.channels = channels
      self.private = private
      self.state = "LOGIN"
      self.me = None
      #it seems really silly to have to put this here, but Python does not allow you to refer to a class within its own definition,
      #ergo this is the next best thing. I've gotta get back into Ruby...
      self.commands = {"commands": (Command.list_commands, "See all documented commands."),
                       "help": (Command.help_command, "Get information on a given command"),
                       "msg" : (Command.msg, "Send a private message."),
                       "part" : (Command.part, "Leave the current room, or a specified room."),
                       "join" : (Command.join, "Join a room, or create a new one if it doesn't already exist."),
                       "quit" : (Command.disconnect, "Leave the server."),
                       "rooms" : (Command.list_rooms, "See a list of active rooms"),
                       "switch" : (Command.switch, "Switch to another room. You will remain in both rooms, but only see messages from the current room."),
                       "topic" : (Command.topic, "Set a new topic for the current room. Note that you must be a channel operator to do this."),
                       "toggleprivate" : (Command.toggleprivate, "Toggle the private setting on a channel. The current channel is affected by default."),
                       "toggleop" : (Command.toggleop, "Toggle operator powers on another user for a given channel. Default is the current channel."),
                       "invite" : (Command.invite, "Invite a user to a channel. Defaults to the current channel. If the channel is private, you must be an op."),
                       "protect" : (Command.protect, "Protect a channel with a (pseudo)random token. Any user without the token will not be able to join."),
                       "unprotect" : (Command.unprotect, "Clear the protection on a channel. Default this channel.")
                       }
      self.signatures = {"commands" : (), "help" : ('cmd',), "msg" : ('user', 'message'), "part" : ('message',),
                         "join" : ('channel', 'topic'), "quit" : ('message',), "rooms": (), "switch": ('channel',), "topic": ('topic',),
                         "toggleprivate": ('channel',), "toggleop": ('other', 'channel'), "invite": ('other', 'channel'), "protect": ('channel',),
                         "unprotect": ('channel',)}
      
   def connectionMade(self):
      self.sendLine("Welcome to DIE: Denizens of the Internet Effusing")
      self.sendLine("Login name?")
      
   def connectionLost(self, reason):
      if self.me.name in self.users:
         del self.users[self.me.name]
         
   def lineReceived(self, line):
      if self.state == "LOGIN":
         self.handle_LOGIN(line)
      else:
         if line[0] == '/':
            self.handle_COMMAND(line[1:])
         else:
            self.handle_CHAT(line)
            
   def handle_LOGIN(self, name):
      if name in self.users:
         self.sendLine("Sorry, name taken.")
         return
      if not name.isalnum():
         self.sendLine("Please use alphanumeric characters only.")
      else:
         self.sendLine("Welcome {0}!".format(name))
         self.me = User(name, self)
         self.users[name] = self.me
         self.state = "NEW TEXACO"
         
   def handle_CHAT(self,message):
      room = self.me.current
      if room is None:
         self.sendLine("\tLike nuclear ash,\n\tyour words fall but on blind eyes.\n\tTry joining a room.")
      else:
         room.chat(self.me, message)
         
   def handle_COMMAND(self, cmd):
      cmd = cmd.split()
      if len(cmd) > 1:
         cmd, args = cmd[0], cmd[1:]
      else:
         cmd, args = cmd[0], [""]
      if cmd not in self.commands:
         self.sendLine('Invalid command. To see a list of commands, type "/commands". For command-specific help, type "/help <command>"')
      else:
         sig = self.signatures[cmd]
         cmd = self.commands[cmd][0]
         _ = []
         if sig == ():
            cmd(self.me)
         else:
            for s in sig:
               if s in ('message', 'topic'):
                  _.append(" ".join(args))
                  break
               else:
                  try:
                     _.append(args.pop(0))
                  except LookupError:
                     pass
            cmd(self.me, *_)
            
class ChatFactory(ServerFactory):
   def __init__(self):
      self.channels = {}
      self.users = {}
      self.private = [0] #making self.private a list ensures that it will be passed by reference, rather than copied.
      
   def buildProtocol(self, addr):
      return ChatProtocol(self.users, self.channels, self.private)

def main():
   import sys
   log.startLogging(sys.stdout)
   reactor.listenTCP(9399, ChatFactory())
   reactor.run()

if __name__ == "__main__":
   main()
