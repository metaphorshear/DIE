from chat import ChatFactory
from twisted.trial import unittest
from twisted.test import proto_helpers

class ChatTestCast2(unittest.TestCase):
   def setUp(self):
      self.factory = ChatFactory()
      self.connections = [self.factory.buildProtocol(('127.0.0.1', 0)) for i in xrange(20)]
      self.trs = [proto_helpers.StringTransport() for a in self.connections]
      for i in xrange(len(self.connections)):
         self.connections[i].makeConnection(self.trs[i])
      
   def _login(self, name, con):
      con.dataReceived(name+'\r\n')
      return self.assertTrue(name in self.factory.users)
      
   def test_part_none(self):
      self._login("A", self.connections[0])
      self.trs[0].clear()
      self.connections[0].dataReceived('/part\r\n')
      return self.assertEqual(self.trs[0].value(), "You are not in a room.\r\n")
      
   def _join(self, name, channel, con):
      self._login(name, con)
      con.dataReceived('/join '+channel+'\r\n')
      return self.assertTrue(con.me in con.channels[channel].users)
      
   def test_join1(self):
      for i in xrange(10):
         self._join('user'+str(i), 'partymansion', self.connections[i])
      self.connections[0].dataReceived('/rooms\r\n')
      return self.assertTrue("10" in self.trs[0].value())
      
   def test_ops(self):
      self.test_join1()
      for i in xrange(4):
         self.connections[0].dataReceived('/toggleop user'+str(i+1)+'\r\n')
      self.connections[4].dataReceived('/toggleprivate\r\n/protect\r\n')
      return self.assertTrue(self.connections[0].channels['partymansion'].private == True and self.connections[0].channels['partymansion'].token != "")
      
   def test_join2(self):
      self.test_ops()
      for i in xrange(5):
         self.connections[i+10].dataReceived('user'+str(i+10)+'\r\n')
         self.trs[i+10].clear()
         self.connections[i+10].dataReceived('/join partymansion\r\n')
      return self.assertTrue("This room is protected, and you lack the necessary authentication token.\r\n" in self.trs[14].value())
      
   def test_invite(self):
      self.test_join2()
      self.trs[11].clear()
      self.connections[2].dataReceived('/invite user11\r\n')
      return self.assertEqual(self.trs[11].value(), "user2 has invited you to join partymansion. If you want to accept, type '/join partymansion'\r\n")
      
   def test_invite2(self):
      self.test_invite()
      self.connections[11].dataReceived('/join partymansion\r\n')
      return self.assertTrue('user1' in self.trs[11].value())
      
   def test_part2(self):
      self.test_ops()
      six = self.connections[6]
      six.dataReceived('/part\r\n')
      self.trs[6].clear()
      six.dataReceived('/join partymansion\r\n')
      return self.assertTrue("This room is protected, and you lack the necessary authentication token.\r\n" in self.trs[6].value())
      
   def test_list_rooms(self):
      self.test_join2()
      self.trs[13].clear()
      self.connections[13].dataReceived('/rooms\r\n')
      return self.assertEqual('No active rooms.\r\n', self.trs[13].value())
      
   def test_list_rooms2(self):
      self.test_list_rooms()
      self.connections[3].dataReceived('/toggleprivate\r\n')
      self.connections[13].dataReceived('/rooms\r\n')
      return self.assertTrue('partymansion' in self.trs[13].value())
      
   def test_chat(self):
      self.test_invite2()
      [u.clear() for u in self.trs]
      self.connections[11].dataReceived('Hi everybody!\r\n')
      return self.assertTrue(all(['user11: Hi everybody!' in self.trs[u].value() for u in [0, 1, 2, 3, 4, 5, 7, 8, 9, 11]]))
      
   
