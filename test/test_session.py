import pickle
import time
from unittest import TestCase

from nose.tools import istest, raises
import redis

from pycket.session import SessionManager, SessionMixin


class SessionMixinTest(TestCase):
    @istest
    def starts_handler_with_session_manager(self):
        class StubHandler(SessionMixin):
            settings = {}

        self.assertIsInstance(StubHandler().session, SessionManager)


class RedisTestCase(TestCase):
    client = None

    def setUp(self):
        if self.client is None:
            self.client = redis.Redis(db=self.DB_NAME)
        self.client.flushdb()


class SessionManagerTest(RedisTestCase):
    DB_NAME = SessionManager.DB_NAME

    @istest
    def sets_session_id_on_cookies(self):
        test_case = self

        class StubHandler(SessionMixin):
            settings = {}
            def get_secure_cookie(self, name):
                test_case.assertEqual(name, 'PYCKET_ID')
                self.cookie_set = True
                return None

            def set_secure_cookie(self, name, value, expire_days):
                test_case.assertEqual(name, 'PYCKET_ID')
                test_case.assertIsInstance(value, basestring)
                test_case.assertGreater(len(value), 0)
                test_case.assertEqual(expire_days, None)
                self.cookie_retrieved = True

        handler = StubHandler()
        session_manager = SessionManager(handler)
        session_manager.set('some-object', 'Some object')

        self.assertTrue(handler.cookie_retrieved)
        self.assertTrue(handler.cookie_set)

    @istest
    def does_not_set_session_id_if_already_exists(self):
        test_case = self

        class StubHandler(SessionMixin):
            settings = {}
            def get_secure_cookie(self, name):
                self.cookie_retrieved = True
                return 'some-id'

        handler = StubHandler()
        session_manager = SessionManager(handler)
        session_manager.set('some-object', 'Some object')

        self.assertTrue(handler.cookie_retrieved)

    @istest
    def saves_session_object_on_redis_with_same_session_id_as_cookie(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        manager.set('some-object', {'foo': 'bar'})

        raw_session = self.client.get(handler.session_id)
        session = pickle.loads(raw_session)

        self.assertEqual(session['some-object']['foo'], 'bar')

    @istest
    def retrieves_session_with_same_data_as_saved(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        manager.set('some-object', {'foo': 'bar'})

        self.assertEqual(manager.get('some-object')['foo'], 'bar')

    @istest
    def keeps_previous_items_when_setting_new_ones(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        manager.set('some-object', {'foo': 'bar'})
        manager.set('some-object2', {'foo2': 'bar2'})

        self.assertEqual(manager.get('some-object')['foo'], 'bar')
        self.assertEqual(manager.get('some-object2')['foo2'], 'bar2')

    @istest
    def retrieves_none_if_session_object_not_previously_set(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        self.assertIsNone(manager.get('unexistant-object'))

    @istest
    def deletes_objects_from_session(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        manager.set('some-object', {'foo': 'bar'})
        manager.set('some-object2', {'foo2': 'bar2'})
        manager.delete('some-object')

        raw_session = self.client.get(handler.session_id)
        session = pickle.loads(raw_session)

        self.assertEqual(session.keys(), ['some-object2'])

    @istest
    def starts_with_1_day_to_expire_in_database(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        one_day = 24 * 60 * 60

        self.assertEqual(manager.EXPIRE_SECONDS, one_day)

    @istest
    def still_retrieves_object_if_not_passed_from_expiration(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        manager.set('foo', 'bar')

        time.sleep(1)

        self.assertEqual(manager.get('foo'), 'bar')

    @istest
    def cannot_retrieve_object_if_passed_from_expiration(self):
        handler = StubHandler()
        manager = SessionManager(handler)
        manager.EXPIRE_SECONDS = 1

        manager.set('foo', 'bar')

        time.sleep(manager.EXPIRE_SECONDS + 1)

        self.assertIsNone(manager.get('foo'))

    @istest
    def repasses_pycket_redis_settings_to_client(self):
        test_case = self
        settings = {'was_retrieved': False}

        class StubSettings(dict):
            def get(self, name, default):
                test_case.assertEqual(name, 'pycket_redis')
                test_case.assertEqual(default, {})
                settings['was_retrieved'] = True
                return default

        handler = StubHandler()
        handler.settings = StubSettings()
        manager = SessionManager(handler)

        self.assertTrue(settings['was_retrieved'])

    @istest
    def retrieves_object_with_dict_key(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        manager.set('foo', 'bar')

        self.assertEqual(manager['foo'], 'bar')

    @istest
    @raises(KeyError)
    def raises_key_error_if_object_doesnt_exist(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        manager['foo']

    @istest
    def sets_object_with_dict_key(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        manager['foo'] = 'bar'

        self.assertEqual(manager['foo'], 'bar')

    @istest
    def gets_default_value_if_provided_and_not_in_bucket(self):
        handler = StubHandler()
        manager = SessionManager(handler)

        value = manager.get('foo', 'Default')

        self.assertEqual(value, 'Default')


class StubHandler(SessionMixin):
    session_id = 'session-id'
    settings = {}

    def get_secure_cookie(self, name):
        return self.session_id
