from chat import ChatFactory
from twisted.trial import unittest
from twisted.test import proto_helpers

class ChatTestCase(unittest.TestCase):
   def setUp(self):
      factory = ChatFactory()
      self.factory = factory
      self.proto = factory.buildProtocol(('127.0.0.1', 0))
      self.tr = proto_helpers.StringTransport()
      self.proto.makeConnection(self.tr)
      self.commands = [a.upper() for a in self.proto.commands.keys()]
      
   def test1(self):
      return self.assertTrue(id(self.factory.users) == id(self.proto.users))
      
   def _test(self, expected):
      data = self.assertEqual(self.tr.value().strip(), expected)
      self.tr.clear()
      return data
      
   def test_welcome(self):
      return self._test("Welcome to DIE: Denizens of the Internet Effusing\r\nLogin name?")
      
   def test_login_bad(self):
      self.test_welcome()
      self.proto.dataReceived('"""_@#$+-*\\\r\n')
      return self._test("Please use alphanumeric characters only.")

   def test_login_bad2(self):
      self.test_login_bad()
      return self.assertTrue('"""_@#$+-*\\' not in self.factory.users)

   def test_login_good(self, name="Blotto"):
      self.test_welcome()
      self.proto.dataReceived(name+"\r\n")
      return self._test("Welcome {0}!".format(name))
      
   def test_login_good2(self, name="Waldo"):
      self.test_login_good(name)
      return self.assertTrue(name in self.factory.users)
      
   def test_commands_bad(self):
      self.test_login_good("Pervo")
      self.proto.dataReceived("/asl\r\n")
      return self._test('Invalid command. To see a list of commands, type "/commands". For command-specific help, type "/help <command>"')

   def test_commands(self):
      self.test_login_good("Curious")
      self.proto.dataReceived("/commands\r\n")
      d = self.assertEqual(set(self.commands), set(self.tr.value().strip().split()))
      self.tr.clear()
      return d
      
   def test_commands_help1(self):
      self.test_login_good("Helpless")
      self.proto.dataReceived("/help\r\n")
      d = self.assertEqual(set(self.commands), set(self.tr.value().strip().split()))
      self.tr.clear()
      return d
      
   def test_commands_help2(self):
      self.test_login_good("Chatty")
      self.proto.dataReceived("/help msg\r\n")
      return self._test("msg\r\nSend a private message.")
      
   def test_chat1(self):
      self.test_login_good("Deck")
      self.proto.dataReceived("'Sup, homie.\r\n")
      return self._test("Like nuclear ash,\n\tyour words fall but on blind eyes.\n\tTry joining a room.")
      
   def test_commands_rooms(self):
      self.test_login_good("Lonesome")
      self.proto.dataReceived("/rooms\r\n")
      return self._test("No active rooms.")
      
   def test_commands_join(self, name="MasterBlaster", channel="#BARTERTOWN"):
      self.test_login_good(name)
      self.proto.dataReceived("/join {0}\r\n".format(channel))
      return self.assertTrue(channel in self.factory.channels)
      
   def test_commands_join2(self, name="Amnesiac", channel="channel"):
      self.test_commands_join(name, channel)
      self.proto.dataReceived("/join {0}\r\n".format(channel))
      return self.assertTrue(len(self.factory.channels[channel].users) == 1)
      
   def test_chat2(self):
      self.test_commands_join("MasterBlaster","#BARTERTOWN")
      self.proto.dataReceived("Who runs #BARTERTOWN?!\r\n")
      return self._test("entering room: #BARTERTOWN\r\n* MasterBlaster (** this is you)\r\nend of list\r\nMasterBlaster: Who runs #BARTERTOWN?!")
      
   def test_part(self):
      self.test_chat2()
      self.proto.dataReceived("/part EMBARGO!\r\n")
      return self._test('User MasterBlaster has left ("EMBARGO!")')
      
   def test_quit(self):
      self.test_chat2()
      self.proto.dataReceived("/quit me dead...\r\n")
      return self._test('User MasterBlaster has left ("me dead...")\r\nBYE')


"""      
   def test_multi1(self):
      for i in xrange(100000):
         self.proto = self.factory.buildProtocol(('127.0.0.1', 0))
         self.tr=proto_helpers.StringTransport()
         self.proto.makeConnection(self.tr)
         self.test_login_good2("user"+str(i))
      return self.assertTrue(len(self.factory.users)==100000)
      
"""
