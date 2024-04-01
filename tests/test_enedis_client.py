#!/usr/bin/python3
# -*- coding: utf-8-
"""
Tests cases on EnedisClient and EnedisApiHelper classes
"""
import json
import logging
import os
import sys
import unittest
from datetime import date, datetime
from unittest.mock import Mock, patch
from mock import MagicMock
from requests import Session, Response
from requests.cookies import cookiejar_from_dict

from enedis_data_connect.enedis_client import DEFAULT_REDIRECT_URI, LOGGER, EnedisClient, TOKEN_TYPE_KEY, ACCESS_TOKEN_KEY, EnedisApiHelper

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, )
_LOGGER: logging.Logger = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)
RESOURCES_DIR = os.path.dirname(__file__) + '/resources/'
CONSUMPTION_PRM: str = '22516914714270'
PRODUCTION_PRM: str = '10284856584123'
CLIENT_ID: str = 'client-1'
CLIENT_SECRET: str = 'client-1-secret-1'
REDIRECT_URL: str = DEFAULT_REDIRECT_URI


def response_from_resource(filename: str) -> Response:
    """
    Return a Response object using data from a file
    :param filename: the name of the file to read
    :return: the Response object
    """
    with open(RESOURCES_DIR + filename, encoding='utf-8') as file:
        data = json.load(file)
        result: Response = Response()
        if 'status_code' in data:
            result.status_code = data['status_code']
        else:
            result.status_code = 200
        if 'encoding' in data:
            result.encoding = data['encoding']
        else:
            result.encoding = 'utf-8'
        if 'content' in data:
            result._content = json.dumps(data['content'], indent=4).encode(result.encoding)
        else:
            result._content = ''
        if 'url' in data:
            result.url = data['url']
        else:
            result.url = ''
        if 'cookies' in data:
            result.cookies = cookiejar_from_dict(data['cookies'])
        else:
            result.cookies = cookiejar_from_dict({})
        result.close = Mock(return_value=None)
        return result


# noinspection SpellCheckingInspection
class EnedisClientTest(unittest.TestCase):
    """
    The test suite for EnedisClient class
    """
    # noinspection PyArgumentList
    def setUp(self, *args, **kwargs) -> None:
        """
        Initialize test case
        :param args: arguments
        :param kwargs: arguments
        """
        super().setUp(*args, **kwargs)
        LOGGER.setLevel(logging.DEBUG)
        self.stream_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
        LOGGER.addHandler(self.stream_handler)
        _LOGGER.info('=> Starting test: %s', self)
        self.client: EnedisClient = EnedisClient(CONSUMPTION_PRM, PRODUCTION_PRM, CLIENT_ID, CLIENT_SECRET)
        self.session: Session = MagicMock(name='mocked session', return_value=object)

    def tearDown(self) -> None:
        """
        Hook method for deconstructing the test fixture after testing it
        """
        if self.client:
            self.client.close()
            self.client = None
        if self.session:
            self.session = None
        LOGGER.removeHandler(self.stream_handler)

    def test_get_client_id(self) -> None:
        """
        Test get_client_id method
        """
        self.assertIsNotNone(self.client.get_client_id())

    def test_get_consumption_prm(self) -> None:
        """
        Test get_consumption_prm method
        """
        self.assertIsNotNone(self.client.get_consumption_prm())

    def test_get_production_prm(self) -> None:
        """
        Test get_production_prm method
        """
        self.assertIsNotNone(self.client.get_production_prm())

    def test_is_connected_when_not_connected(self) -> None:
        """
        Test is_connected when not connected
        """
        self.assertFalse(self.client.is_connected())
        self.assertIsNone(self.client.get_token_data())

        self.session.send = Mock(return_value=response_from_resource('revoke.json'))
        self.client.close()

        self.assertFalse(self.client.is_connected())
        self.assertIsNone(self.client.get_token_data())

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_is_connected_when_connected(self, new_session_mock) -> None:
        """
        Test is_connected when connected
        """
        self.session.send = Mock(return_value=response_from_resource('authentication.json'))
        new_session_mock.return_value = self.session
        self.client.connect()

        self.assertTrue(self.client.is_connected())
        self.assertIsNotNone(self.client.get_token_data())
        self.assertIsNotNone(self.client.get_token_data()[TOKEN_TYPE_KEY])
        self.assertIsNotNone(self.client.get_token_data()[ACCESS_TOKEN_KEY])

        self.session.send = Mock(return_value=response_from_resource('revoke.json'))
        self.client.close()

        self.assertFalse(self.client.is_connected())
        self.assertIsNone(self.client.get_token_data())
        self.assertTrue(self.client.get_request_count() > 0)
        self.assertTrue(self.client.get_errors_count() == 0)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_connect(self, new_session_mock) -> None:
        """
        Test the connect method
        """
        self.session.send = Mock(return_value=response_from_resource('authentication.json'))
        new_session_mock.return_value = self.session
        self.client.connect()

        self.assertIsNotNone(self.client.get_token_data())
        self.assertIsNotNone(self.client.get_token_data()[TOKEN_TYPE_KEY])
        self.assertIsNotNone(self.client.get_token_data()[ACCESS_TOKEN_KEY])
        self.assertTrue(self.client.get_request_count() > 0)
        self.assertTrue(self.client.get_errors_count() == 0)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_close_when_not_connected(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(return_value=response_from_resource('revoke.json'))
        new_session_mock.return_value = self.session

        self.client.close()

        self.assertFalse(self.client.is_connected())
        self.assertIsNone(self.client.get_token_data())
        self.assertTrue(self.client.get_request_count() > 0)
        self.assertTrue(self.client.get_errors_count() == 0)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_close_when_connected(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(return_value=response_from_resource('authentication.json'))
        new_session_mock.return_value = self.session
        self.client.connect()

        self.assertIsNotNone(self.client.get_token_data())
        self.assertIsNotNone(self.client.get_token_data()[TOKEN_TYPE_KEY])
        self.assertIsNotNone(self.client.get_token_data()[ACCESS_TOKEN_KEY])

        self.session.send = Mock(return_value=response_from_resource('revoke.json'))
        self.client.close()

        self.assertFalse(self.client.is_connected())
        self.assertIsNone(self.client.get_token_data())
        self.assertTrue(self.client.get_request_count() > 0)
        self.assertTrue(self.client.get_errors_count() == 0)


# noinspection SpellCheckingInspection
class EnedisApiHelperTest(unittest.TestCase):
    """
    The test suite for EnedisApiHelper class
    """
    # noinspection PyArgumentList
    def setUp(self, *args, **kwargs) -> None:
        """
        Initialize test case
        :param args: arguments
        :param kwargs: arguments
        """
        super().setUp(*args, **kwargs)
        LOGGER.setLevel(logging.DEBUG)
        self.stream_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
        LOGGER.addHandler(self.stream_handler)
        _LOGGER.info('=> Starting test: %s', self)
        self.client: EnedisClient = EnedisClient(CONSUMPTION_PRM, PRODUCTION_PRM, CLIENT_ID, CLIENT_SECRET)
        self.session: Session = MagicMock(name='mocked session', return_value=object)
        self.helper: EnedisApiHelper = EnedisApiHelper(self.client)

    def tearDown(self) -> None:
        """
        Hook method for deconstructing the test fixture after testing it
        """
        if self.client:
            self.client.close()
            self.client = None
        if self.session:
            self.session = None
        LOGGER.removeHandler(self.stream_handler)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_consumption_with_invalid_token(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('expired_authentication.json'),
            response_from_resource('authentication.json'),
            response_from_resource('daily_consumption.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        end_date: date = date(2021, 9, 22)

        self.client.connect()
        result: dict[date, int] = self.helper.get_daily_consumption(start_date, end_date)

        self.assertIsNotNone(result)
        self.assertEqual(8, len(result))

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_consumption_without_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_consumption.json')
        ])
        new_session_mock.return_value = self.session
        # noinspection PyTypeChecker
        start_date: date = None
        end_date: date = date(2021, 9, 22)

        with self.assertRaises(ValueError):
            self.helper.get_daily_consumption(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_consumption_without_end_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_consumption.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        # noinspection PyTypeChecker
        end_date: date = None

        with self.assertRaises(ValueError):
            self.helper.get_daily_consumption(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_consumption_with_end_date_lower_than_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_consumption.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 22)
        end_date: date = date(2021, 9, 14)

        with self.assertRaises(ValueError):
            self.helper.get_daily_consumption(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_consumption(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_consumption.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        end_date: date = date(2021, 9, 22)

        result: dict[date, int] = self.helper.get_daily_consumption(start_date, end_date)

        self.assertIsNotNone(result)
        self.assertEqual(8, len(result))
        for k, v in result.items():
            self.assertIsNotNone(k)
            self.assertIsInstance(k, date)
            self.assertTrue(k.year == 2021)
            self.assertTrue(k.month == 9)
            self.assertTrue(k.day >= 14)
            self.assertTrue(k.day <= 22)
            self.assertIsNotNone(v)
            self.assertIsInstance(v, int)
            self.assertTrue(v >= 26429)
            self.assertTrue(v <= 49171)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_consumption_load_curve_without_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('consumption_load_curve.json')
        ])
        new_session_mock.return_value = self.session
        # noinspection PyTypeChecker
        start_date: date = None
        end_date: date = date(2021, 9, 22)

        with self.assertRaises(ValueError):
            self.helper.get_consumption_load_curve(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_consumption_load_curve_without_end_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('consumption_load_curve.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        # noinspection PyTypeChecker
        end_date: date = None

        with self.assertRaises(ValueError):
            self.helper.get_consumption_load_curve(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_consumption_load_curve_with_end_date_lower_than_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_consumption.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 22)
        end_date: date = date(2021, 9, 14)

        with self.assertRaises(ValueError):
            self.helper.get_consumption_load_curve(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_consumption_load_curve(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('consumption_load_curve.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        end_date: date = date(2021, 9, 22)

        result: dict[datetime, int] = self.helper.get_consumption_load_curve(start_date, end_date)

        self.assertIsNotNone(result)
        self.assertEqual(48, len(result))
        for k, v in result.items():
            self.assertIsNotNone(k)
            self.assertIsInstance(k, datetime)
            self.assertTrue(k.year == 2021)
            self.assertTrue(k.month == 9)
            self.assertTrue(k.day >= 14)
            self.assertTrue(k.day <= 22)
            self.assertIsNotNone(v)
            self.assertIsInstance(v, int)
            self.assertTrue(v >= 261)
            self.assertTrue(v <= 3554)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_max_daily_consumed_power_without_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('max_daily_consumed_power.json')
        ])
        new_session_mock.return_value = self.session
        # noinspection PyTypeChecker
        start_date: date = None
        end_date: date = date(2021, 9, 22)

        with self.assertRaises(ValueError):
            self.helper.get_max_daily_consumed_power(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_max_daily_consumed_power_without_end_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('max_daily_consumed_power.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        # noinspection PyTypeChecker
        end_date: date = None

        with self.assertRaises(ValueError):
            self.helper.get_max_daily_consumed_power(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_max_daily_consumed_power_with_end_date_lower_than_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('max_daily_consumed_power.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 22)
        end_date: date = date(2021, 9, 14)

        with self.assertRaises(ValueError):
            self.helper.get_max_daily_consumed_power(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_max_daily_consumed_power(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('max_daily_consumed_power.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        end_date: date = date(2021, 9, 22)

        result: dict[date, int] = self.helper.get_max_daily_consumed_power(start_date, end_date)

        self.assertIsNotNone(result)
        self.assertEqual(8, len(result))
        for k, v in result.items():
            self.assertIsNotNone(k)
            self.assertIsInstance(k, date)
            self.assertTrue(k.year == 2021)
            self.assertTrue(k.month == 9)
            self.assertTrue(k.day >= 14)
            self.assertTrue(k.day <= 22)
            self.assertIsNotNone(v)
            self.assertIsInstance(v, int)
            self.assertTrue(v >= 1287)
            self.assertTrue(v <= 7287)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_production_with_invalid_token(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('expired_authentication.json'),
            response_from_resource('authentication.json'),
            response_from_resource('daily_production.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        end_date: date = date(2021, 9, 22)

        self.client.connect()
        result: dict[date, int] = self.helper.get_daily_production(start_date, end_date)

        self.assertIsNotNone(result)
        self.assertEqual(8, len(result))

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_production_without_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_production.json')
        ])
        new_session_mock.return_value = self.session
        # noinspection PyTypeChecker
        start_date: date = None
        end_date: date = date(2021, 9, 22)

        with self.assertRaises(ValueError):
            self.helper.get_daily_production(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_production_without_end_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_production.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        # noinspection PyTypeChecker
        end_date: date = None

        with self.assertRaises(ValueError):
            self.helper.get_daily_production(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_production_with_end_date_lower_than_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_production.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 22)
        end_date: date = date(2021, 9, 14)

        with self.assertRaises(ValueError):
            self.helper.get_daily_production(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_daily_production(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_production.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        end_date: date = date(2021, 9, 22)

        result: dict[date, int] = self.helper.get_daily_production(start_date, end_date)

        self.assertIsNotNone(result)
        self.assertEqual(8, len(result))
        for k, v in result.items():
            self.assertIsNotNone(k)
            self.assertIsInstance(k, date)
            self.assertTrue(k.year == 2021)
            self.assertTrue(k.month == 9)
            self.assertTrue(k.day >= 14)
            self.assertTrue(k.day <= 22)
            self.assertIsNotNone(v)
            self.assertIsInstance(v, int)
            self.assertTrue(v >= 26429)
            self.assertTrue(v <= 49171)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_production_load_curve_without_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('production_load_curve.json')
        ])
        new_session_mock.return_value = self.session
        # noinspection PyTypeChecker
        start_date: date = None
        end_date: date = date(2021, 9, 22)

        with self.assertRaises(ValueError):
            self.helper.get_production_load_curve(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_production_load_curve_without_end_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('production_load_curve.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        # noinspection PyTypeChecker
        end_date: date = None

        with self.assertRaises(ValueError):
            self.helper.get_production_load_curve(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_production_load_curve_with_end_date_lower_than_start_date(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('daily_production.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 22)
        end_date: date = date(2021, 9, 14)

        with self.assertRaises(ValueError):
            self.helper.get_production_load_curve(start_date, end_date)

    @patch('enedis_data_connect.enedis_client.EnedisClient._new_session')
    def test_get_production_load_curve(self, new_session_mock) -> None:
        """
        Test the close method
        """
        self.session.send = Mock(side_effect=[
            response_from_resource('authentication.json'),
            response_from_resource('production_load_curve.json')
        ])
        new_session_mock.return_value = self.session
        start_date: date = date(2021, 9, 14)
        end_date: date = date(2021, 9, 22)

        result: dict[datetime, int] = self.helper.get_production_load_curve(start_date, end_date)

        self.assertIsNotNone(result)
        self.assertEqual(48, len(result))
        for k, v in result.items():
            self.assertIsNotNone(k)
            self.assertIsInstance(k, datetime)
            self.assertTrue(k.year == 2021)
            self.assertTrue(k.month == 9)
            self.assertTrue(k.day >= 14)
            self.assertTrue(k.day <= 22)
            self.assertIsNotNone(v)
            self.assertIsInstance(v, int)
            self.assertTrue(v >= 261)
            self.assertTrue(v <= 3554)
