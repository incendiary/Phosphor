import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from inc.mq_includes import create_mq_routing_key

try:
    from unittest.mock import MagicMock, patch, call
except ImportError:
    from mock import MagicMock, patch, call

from inc import mq_includes


class TestCreateMqRoutingKey(unittest.TestCase):

    def test_basename_only(self):
        self.assertEqual(create_mq_routing_key('users'), 'users')

    def test_with_prepend(self):
        self.assertEqual(create_mq_routing_key('app', prepend='uid1_env1_'), 'uid1_env1_app')

    def test_with_append(self):
        self.assertEqual(create_mq_routing_key('app', apend='_suffix'), 'app_suffix')

    def test_with_prepend_and_append(self):
        result = create_mq_routing_key('app', prepend='pre_', apend='_suf')
        self.assertEqual(result, 'pre_app_suf')

    def test_none_prepend_ignored(self):
        self.assertEqual(create_mq_routing_key('cics', prepend=None), 'cics')

    def test_none_append_ignored(self):
        self.assertEqual(create_mq_routing_key('cics', apend=None), 'cics')


class TestQueDecWithMock(unittest.TestCase):

    def test_declares_queue(self):
        mock_channel = MagicMock()
        mq_includes.que_dec(mock_channel, 'test_queue')
        mock_channel.queue_declare.assert_called_once_with(queue='test_queue', durable=True)

    def test_destructive_deletes_first(self):
        mock_channel = MagicMock()
        mq_includes.que_dec(mock_channel, 'test_queue', destructive=True)
        mock_channel.queue_delete.assert_called_once_with(queue='test_queue')
        mock_channel.queue_declare.assert_called_once()

    def test_non_destructive_does_not_delete(self):
        mock_channel = MagicMock()
        mq_includes.que_dec(mock_channel, 'test_queue', destructive=False)
        mock_channel.queue_delete.assert_not_called()


class TestMqBasicPublish(unittest.TestCase):

    def test_publishes_with_correct_args(self):
        mock_channel = MagicMock()
        mq_includes.mq_basic_publish(mock_channel, 'my_queue', 'abc')
        mock_channel.basic_publish.assert_called_once()
        call_kwargs = mock_channel.basic_publish.call_args
        self.assertEqual(call_kwargs[1]['routing_key'], 'my_queue')
        self.assertEqual(call_kwargs[1]['body'], 'abc')

    def test_routing_key_lowercased(self):
        mock_channel = MagicMock()
        mq_includes.mq_basic_publish(mock_channel, 'MY_QUEUE', 'body')
        call_kwargs = mock_channel.basic_publish.call_args
        self.assertEqual(call_kwargs[1]['routing_key'], 'my_queue')


if __name__ == '__main__':
    unittest.main()
