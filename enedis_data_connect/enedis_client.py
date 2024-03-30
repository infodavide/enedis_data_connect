#!/usr/bin/python3
# -*- coding: utf-8-
"""
The Enedis data-connect client
"""
import base64
import json
import logging
import re
from datetime import datetime, date
from threading import RLock
from typing import Any
from homeassistant import exceptions
from homeassistant.core import HomeAssistant
from requests import PreparedRequest, Session, Request, Response

from .const import ENDPOINT_TOKEN_URL, DEFAULT_REDIRECT_URI, ENDPOINT_URL, LOGGER
from .utils import Singleton

_LOGGER = logging.getLogger(__name__)
_DATE_FORMAT: str = '%Y-%m-%d'
_DATE_TIME_FORMAT: str = '%Y-%m-%d %H:%M:%S'
_RETRIES_COUNT: int = 3

TOKEN_TYPE_KEY: str = 'token_type'
ACCESS_TOKEN_KEY: str = 'access_token'
_METER_READING_KEY: str = 'meter_reading'
_INTERVAL_READING_KEY: str = 'interval_reading'
_VALUE_KEY: str = 'value'
_DATE_KEY: str = 'date'

_AUTHORIZATION_HEADER: str = 'Authorization'
_ACCEPT_HEADER: str = 'Accept'

_START_PARAM: str = 'start'
_END_PARAM: str = 'end'
_USAGE_POINT_ID: str = 'usage_point_id'


class InvalidClientId(exceptions.HomeAssistantError):
    """
    Error to indicate that PDL is invalid
    """


class InvalidClientSecret(exceptions.HomeAssistantError):
    """
    Error to indicate that PDL is invalid
    """


class InvalidPdl(exceptions.HomeAssistantError):
    """
    Error to indicate that PDL is invalid
    """


class InvalidUrl(exceptions.HomeAssistantError):
    """
    Error to indicate that URL is invalid
    """


class InvalidToken(exceptions.HomeAssistantError):
    """
    Error to indicate that token is invalid
    """


class InvalidScanInterval(exceptions.HomeAssistantError):
    """
    Error to indicate that scan interval is invalid
    """


class InvalidPeakHourCost(exceptions.HomeAssistantError):
    """
    Error to indicate that cost of a peak hour is invalid
    """


class InvalidAccess(exceptions.HomeAssistantError):
    """
    Error to indicate that token or PDL are not authorized
    """


class ApiRequestError(exceptions.HomeAssistantError):
    """
    Error to indicate that request failed
    """


class EnedisClient(metaclass=Singleton):
    """
    The Enedis data-connect client
    """

    # noinspection PyTypeChecker
    def __init__(self, hass: HomeAssistant, pdl: str, client_id: str, client_secret: str, redirect_uri: str = DEFAULT_REDIRECT_URI):
        """
        The constructor
        :param hass: the home assistant instance
        :param pdl: the PDL identifier
        :param client_id: the client identifier
        :param client_secret: the client secret
        :param redirect_uri: the redirection URI
        """
        self._logger = logging.getLogger(__class__.__name__)
        for handler in LOGGER.handlers:
            self._logger.addHandler(handler)
            self._logger.setLevel(LOGGER.level)
        self._logger.debug("Building a %s", __class__.__name__)
        self._logger.debug("Building the client with: PDL: %s, Client identifier: %s, redirect URL: %s and secret: %s", pdl, client_id, redirect_uri, re.sub(r'.', '*', client_secret))
        if pdl is None or not re.match("\\d{14}", pdl):
            raise InvalidPdl
        if redirect_uri is None or not re.match('^(http|https):.*$', redirect_uri):  # Note that validators.url does not validate URL with localhost or some special characters
            raise InvalidUrl
        if client_id is None or len(client_id) <= 0 or len(client_id) > 128:
            raise InvalidClientId
        if client_secret is None or len(client_secret) <= 0 or len(client_secret) > 128:
            raise InvalidClientSecret
        self._hass: HomeAssistant = hass
        self._lock: RLock = RLock()
        self._pdl: str = pdl
        self._client_id: str = client_id
        self._client_secret: bytes = base64.b64encode(client_secret.encode('utf-8'))
        self._redirect_uri: str = DEFAULT_REDIRECT_URI
        if redirect_uri is not None and len(redirect_uri) > 0:
            self._redirect_uri = redirect_uri
        self._token_data: dict[str, Any] = None
        self._request_count: int = 0
        self._errors_count: int = 0

    def __del__(self):
        """
        Destructor
        """
        self._hass.async_add_executor_job(self.close)

    def _log_request(self, req: PreparedRequest) -> None:
        """
        Log the HTTP request
        :param req: the request
        """
        # pylint: disable=logging-format-interpolation,consider-using-f-string
        self._logger.debug('\n{}\n{}\n{}\n{}\n{}\n'.format(
            '-----------REQUEST START-----------',
            req.method + ' ' + req.url,
            '\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
            req.body,
            '-----------REQUEST STOP-----------',
        ))
        # pylint: enable=logging-format-interpolation,consider-using-f-string

    def _log_response(self, resp: Response) -> None:
        """
        Log the response
        :param resp:  the response
        """
        # pylint: disable=logging-format-interpolation,consider-using-f-string
        self._logger.debug('\n{}\n{}\n{}\n{}\n{}\n'.format(
            '-----------RESPONSE START-----------',
            str(resp.status_code) + ' ' + resp.url,
            '\n'.join('{}: {}'.format(k, v) for k, v in resp.cookies.items()),
            resp.text,
            '-----------RESPONSE STOP-----------',
        ))
        # pylint: enable=logging-format-interpolation,consider-using-f-string

    def _get_headers(self, headers: dict[str, str] = None) -> dict[str, str]:
        """
        Return the headers
        :param headers: the headers
        :return: the headers with authentication if available
        """
        result: dict[str, str] = headers
        if not result:
            result = {}
        if self._token_data:
            token_type: str = self._token_data['token_type']
            token: str = self._token_data['access_token']
            if TOKEN_TYPE_KEY in self._token_data:
                token_type = self._token_data[TOKEN_TYPE_KEY]
            if ACCESS_TOKEN_KEY in self._token_data:
                token = self._token_data[ACCESS_TOKEN_KEY]
            if token_type and token:
                result[_AUTHORIZATION_HEADER] = token_type + ' ' + token
        if _ACCEPT_HEADER not in result:
            result[_ACCEPT_HEADER] = 'application/json'
        return result

    # noinspection PyMethodMayBeStatic
    def _new_session(self) -> Session:
        """
        Return e new HTTP session
        Useful for testing
        :return: the new session instance
        """
        return Session()

    def get_data(self, url: str, headers: dict[str, str] = None, params: dict[str, str] = None, data: dict[str, str] = None, auto_connect: bool = True) -> dict[str, Any]:
        """
        Retrieves the data
        :param url: the url
        :param headers: the headers
        :param params: the parameters
        :param data: the data
        :param auto_connect: true to auto connect the client
        :return: the data of the response
        """
        self._logger.debug('Retrieving data using parameters: %s, headers: %s, data: %s, auto-connect: %s ', params, headers, data, auto_connect)
        self._request_count += 1
        # noinspection PyTypeChecker
        exception: Exception = None
        tries: int = 0
        with self._lock:
            while tries < _RETRIES_COUNT:
                if auto_connect and not self.is_connected():
                    self.connect()
                req: Request = Request("GET", url, headers=self._get_headers(headers), params=params, data=data)
                prepared_req = req.prepare()
                self._log_request(prepared_req)
                http_session: Session = self._new_session()
                http_session.verify = True
                # noinspection PyTypeChecker
                resp: Response = None
                tries += 1
                # noinspection PyBroadException
                try:
                    resp = http_session.send(prepared_req)
                    self._log_response(resp)
                    if resp.status_code == 401:
                        self._logger.warning("Token expired, trying to re-authenticate...")
                        self._token_data = None
                        self.connect()
                    elif resp.status_code == 200:
                        return json.loads(resp.text)
                    else:
                        raise InvalidAccess
                except Exception as e:  # pylint: disable=broad-except
                    exception = e
                finally:
                    if resp:
                        resp.close()
                    if http_session:
                        http_session.close()
        self._errors_count += 1
        self._logger.exception("An error occurred while requesting the API")
        raise ApiRequestError(exception) from exception

    def post_data_with_result(self, url: str, headers: dict[str, str] = None, params: dict[str, str] = None, data: dict[str, str] = None, auto_connect: bool = True) -> dict[str, Any]:
        """
        Send returning data
        :param url: the url
        :param headers: the headers
        :param params: the parameters
        :param data: the data
        :param auto_connect: true to auto connect the client
        :return: the data of the response
        """
        req: Request = Request("POST", url, headers=self._get_headers(headers), params=params, data=data)
        prepared_req = req.prepare()
        self._log_request(prepared_req)
        self._request_count += 1
        # noinspection PyTypeChecker
        exception: Exception = None
        tries: int = 0
        with self._lock:
            while tries < _RETRIES_COUNT:
                if auto_connect and not self.is_connected():
                    self.connect()
                http_session: Session = self._new_session()
                http_session.verify = True
                # noinspection PyTypeChecker
                resp: Response = None
                tries += 1
                # noinspection PyBroadException
                try:
                    resp = http_session.send(prepared_req)
                    self._log_response(resp)
                    if resp.status_code == 401:
                        self._logger.warning("Token expired, trying to re-authenticate...")
                        self._token_data = None
                        self.connect()
                    elif resp.status_code == 200:
                        return json.loads(resp.text)
                    else:
                        raise InvalidAccess
                except Exception as e:  # pylint: disable=broad-except
                    exception = e
                finally:
                    if resp:
                        resp.close()
                    if http_session:
                        http_session.close()
        self._errors_count += 1
        self._logger.exception("An error occurred while requesting the API")
        raise ApiRequestError(exception) from exception

    def post_data_without_result(self, url: str, headers: dict[str, str], params: dict[str, str], data: dict[str, str], auto_connect: bool = True) -> None:
        """
        Send without returning data
        :param url: the url
        :param headers: the headers
        :param params: the parameters
        :param data: the data
        :param auto_connect: true to auto connect the client
        """
        req: Request = Request("POST", url, headers=self._get_headers(headers), params=params, data=data)
        prepared_req = req.prepare()
        self._log_request(prepared_req)
        self._request_count += 1
        # noinspection PyTypeChecker
        exception: Exception = None
        tries: int = 0
        with self._lock:
            while tries < _RETRIES_COUNT:
                if auto_connect and not self.is_connected():
                    self.connect()
                http_session: Session = self._new_session()
                http_session.verify = True
                # noinspection PyTypeChecker
                resp: Response = None
                tries += 1
                # noinspection PyBroadException
                try:
                    resp = http_session.send(prepared_req)
                    self._log_response(resp)
                    if resp.status_code == 401:
                        self._logger.warning("Token expired, trying to re-authenticate...")
                        self._token_data = None
                        self.connect()
                    elif resp.status_code == 200:
                        return
                    else:
                        raise InvalidAccess
                except Exception as e:  # pylint: disable=broad-except
                    exception = e
                finally:
                    if resp:
                        resp.close()
                    if http_session:
                        http_session.close()
        self._errors_count += 1
        self._logger.exception("An error occurred while requesting the API")
        raise ApiRequestError(exception) from exception

    # noinspection PyTypeChecker
    def close(self):
        """
        Close the client
        """
        if not self.is_connected():
            self._logger.debug("Client already disconnected")
            return
        self._logger.info("Closing client...")
        req_headers: dict[str, str] = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        req_params: dict[str, str] = {
        }
        req_data: dict[str, str] = {
            'client_id': self._client_id,
            'client_secret':  self._get_client_secret(),
            'token': self._token_data['access_token']
        }
        # noinspection PyBroadException
        try:
            self.post_data_without_result(ENDPOINT_TOKEN_URL + 'revoke', req_headers, req_params, req_data, auto_connect = False)
        except Exception:  # pylint: disable=broad-except
            self._logger.exception("An error occurred while closing the client")
        self._token_data = None

    def get_pdl(self) -> str:
        """
        Get the PDL identifier
        :return: the PDL identifier
        """
        return self._pdl

    def get_client_id(self) -> str:
        """
        Get the client identifier
        :return: the identifier
        """
        return self._client_id

    def _get_client_secret(self) -> str | None:  # pylint: disable=unsupported-binary-operation
        """
        Get the client secret
        :return: the secret
        """
        if self._client_secret is None:
            return None
        return base64.b64decode(self._client_secret).decode('utf-8')

    def get_token_data(self) -> dict[str, Any]:
        """
        Get the current token data
        :return: the data
        """
        return self._token_data

    def get_request_count(self) -> int:
        """
        Return the number of requests
        :return: the number of requests
        """
        return self._request_count

    def get_errors_count(self) -> int:
        """
        Return the number of errors
        :return: the number of errors
        """
        return self._errors_count

    def is_connected(self) -> bool:
        """
        Return true if the connection has been initialized
        :return:
        :rtype:
        """
        return self._token_data is not None and len(self._token_data) > 0

    # noinspection PyTypeChecker
    def connect(self) -> None:
        """
        Connect the client
        """
        if self.is_connected():
            self._logger.debug("Client already connected")
            return
        self._logger.info("Connecting client...")
        req_headers: dict[str, str] = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        req_params: dict[str, str] = {
            'redirect_uri': self._redirect_uri,
        }
        req_data: dict[str, str] = {
            'grant_type': 'client_credentials',
            'client_id': self._client_id,
            'client_secret': self._get_client_secret()
        }
        self._token_data = self.post_data_with_result(ENDPOINT_TOKEN_URL + 'token', req_headers, req_params, req_data, auto_connect = False)
        self._logger.debug("Token data is: %s", self._token_data)


class EnedisApiHelper:
    """
    The API helper
    """

    # noinspection PyTypeChecker
    def __init__(self, client: EnedisClient):
        """
        The constructor
        :param client:  the client
        """
        self._logger = logging.getLogger(__class__.__name__)
        for handler in LOGGER.handlers:
            self._logger.addHandler(handler)
            self._logger.setLevel(LOGGER.level)
        self._logger.debug("Building a %s", __class__.__name__)
        self._client: EnedisClient = client
        self._max_daily_consumed_power_request_date: datetime = None
        self._max_daily_consumed_power_request_end_date: date = None
        self._daily_consumption_request_date: datetime = None
        self._daily_consumption_request_end_date: date = None
        self._consumption_load_curve_request_date: datetime = None
        self._consumption_load_curve_request_end_date: date = None

    # noinspection PyTypeChecker
    def reset(self, request_dates: bool = False) -> None:
        """
        Reset the stored parameters and execution dates of the requests
        :param request_dates: true to reset the execution dates of the requests
        """
        self._logger.warning("Resetting counters")
        if request_dates:
            self._max_daily_consumed_power_request_date: datetime = None
            self._daily_consumption_request_date: datetime = None
            self._consumption_load_curve_request_date: datetime = None
        self._max_daily_consumed_power_request_end_date: date = None
        self._daily_consumption_request_end_date: date = None
        self._consumption_load_curve_request_end_date: date = None

    def get_max_daily_consumed_power(self, start_date: date, end_date: date) -> dict[datetime, int]:
        """
        Return the maximum consumed power per day
        :param start_date: the start date
        :param end_date: the end date
        :return: the dictionary describing values indexed by the date
        """
        if not start_date:
            raise ValueError('Start date is not valid')
        if not end_date:
            raise ValueError('End date is not valid')
        if start_date > end_date:
            raise ValueError('End date must be greater than start date')
        self._logger.debug('Retrieving maximum daily consumed power...')
        req_params = {
            _START_PARAM: start_date.strftime(_DATE_FORMAT),
            _END_PARAM: end_date.strftime(_DATE_FORMAT),
            _USAGE_POINT_ID: self._client.get_pdl()
        }
        # noinspection SpellCheckingInspection
        data: dict[str, Any] = self._client.get_data(f'{ENDPOINT_URL}/metering_data_dcmp/v5/daily_consumption_max_power', params=req_params)
        self._max_daily_consumed_power_request_date = datetime.now()
        self._max_daily_consumed_power_request_end_date = end_date
        result: dict[datetime, int] = {}
        if data and _METER_READING_KEY in data:
            meter_reading: dict[str, Any] = data[_METER_READING_KEY]
            if _INTERVAL_READING_KEY in meter_reading:
                intervals: list[dict[str, Any]] = meter_reading[_INTERVAL_READING_KEY]
                if intervals:
                    for interval in intervals:
                        if _DATE_KEY in interval and _VALUE_KEY in interval:
                            result[datetime.strptime(interval[_DATE_KEY], _DATE_TIME_FORMAT)] = int(interval[_VALUE_KEY])
        self._logger.debug('%s items retrieved', len(result))
        return result

    def get_daily_consumption(self, start_date: date, end_date: date) -> dict[date, int]:
        """
        Return the consumption per day
        :param start_date: the start date
        :param end_date: the end date
        :return: the dictionary describing values indexed by the date
        """
        if not start_date:
            raise ValueError('Start date is not valid')
        if not end_date:
            raise ValueError('End date is not valid')
        if start_date > end_date:
            raise ValueError('End date must be greater than start date')
        self._logger.debug('Retrieving daily consumption...')
        req_params = {
            _START_PARAM: start_date.strftime(_DATE_FORMAT),
            _END_PARAM: end_date.strftime(_DATE_FORMAT),
            _USAGE_POINT_ID: self._client.get_pdl()
        }
        # noinspection SpellCheckingInspection
        data: dict[str, Any] = self._client.get_data(f'{ENDPOINT_URL}/metering_data_dc/v5/daily_consumption', params=req_params)
        self._daily_consumption_request_date = datetime.now()
        self._daily_consumption_request_end_date = end_date
        result: dict[date, int] = {}
        if data and _METER_READING_KEY in data:
            meter_reading: dict[str, Any] = data[_METER_READING_KEY]
            if _INTERVAL_READING_KEY in meter_reading:
                intervals: list[dict[str, Any]] = meter_reading[_INTERVAL_READING_KEY]
                if intervals:
                    for interval in intervals:
                        if _DATE_KEY in interval and _VALUE_KEY in interval:
                            result[datetime.strptime(interval[_DATE_KEY], _DATE_FORMAT).date()] = int(interval[_VALUE_KEY])
        self._logger.debug('%s items retrieved', len(result))
        return result

    def get_consumption_load_curve(self, start_date: date, end_date: date) -> dict[datetime, int]:
        """
        Return the consumption per available period defined by the API
        This API provides data each 30 minutes
        :param start_date: the start date
        :param end_date: the end date
        :return: the dictionary describing values indexed by the date
        """
        if not start_date:
            raise ValueError('Start date is not valid')
        if not end_date:
            raise ValueError('End date is not valid')
        if start_date > end_date:
            raise ValueError('End date must be greater than start date')
        self._logger.debug('Retrieving consumption load curve...')
        req_params = {
            _START_PARAM: start_date.strftime(_DATE_FORMAT),
            _END_PARAM: end_date.strftime(_DATE_FORMAT),
            _USAGE_POINT_ID: self._client.get_pdl()
        }
        # noinspection SpellCheckingInspection
        data: dict[str, Any] = self._client.get_data(f'{ENDPOINT_URL}/metering_data_clc/v5/consumption_load_curve', params=req_params)
        self._logger.debug('%s items retrieved', len(data))
        self._consumption_load_curve_request_date = datetime.now()
        self._consumption_load_curve_request_end_date = end_date
        result: dict[datetime, int] = {}
        if data and _METER_READING_KEY in data:
            meter_reading: dict[str, Any] = data[_METER_READING_KEY]
            if _INTERVAL_READING_KEY in meter_reading:
                intervals: list[dict[str, Any]] = meter_reading[_INTERVAL_READING_KEY]
                if intervals:
                    for interval in intervals:
                        if _DATE_KEY in interval and _VALUE_KEY in interval:
                            result[datetime.strptime(interval[_DATE_KEY], _DATE_TIME_FORMAT)] = int(interval[_VALUE_KEY])
        self._logger.debug('%s items retrieved', len(result))
        return result
