import json
import requests
import urllib3
import logging
from collections import namedtuple
from time import time
import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TerneoParam = namedtuple('TerneoParam', ['readValue', 'setValue', 'type', 'divider'])

terneo_params_map = {
    0: ("startAwayTime", 6),  # в секундах от 01.01.2000, время начала отъезда
    1: ("endAwayTime", 6),  # в секундах от 01.01.2000, время конца отъезда
    2: ("mode", 2),  # режим работы: расписание=0, ручной=1
    3: ("controlType", 2),  # режим контроля: по полу=0, по воздуху=1, расширенный=2
    4: ("manualAir", 1), # в °C, уставка ручного режима по воздуху
    5: ("manualFloorTemperature", 1),  # в °C, уставка ручного режима по полу
    6: ("awayAirTemperature", 1),  # в °C, уставка режима отъезда по воздуху
    7: ("awayFloorTemperature", 1),  # в °C, уставка режима отъезда по полу
    14: ("minTempAdvancedMode", 2),  # в °C, минимальная температура пола в расширенном режиме
    15: ("maxTempAdvancedMode", 2),  # в °C, максимальная температура пола в расширенном режиме
    17: ("power", 4),  # в у.е., P=(power<=150)?(power*10):(1500+power*20), подключенная мощность
    18: ("sensorType", 2),
    # тип подключенного аналогового датчика температуры: 4,7кОм=0, 6,8кОм=1, 10кОм=2, 12кОм=3, 15кОм=4, 33кОм=5, 47кОм=6
    19: ("histeresis", 2),  # в 1/10 °C, гистерезис
    20: ("airCorrection", 1),  # в 1/10 °C, поправка датчика воздуха
    21: ("floorCorrection", 1),  # в 1/10 °C, поправка датчика пола
    23: ("brightness", 2),  # в у.е. (от 0 до 9) яркость
    25: ("propKoef", 3),  # в минутах включенной нагрузки в пределах 30 минутного цикла работы пропорционального режима
    26: ("upperLimit", 1),  # в °C, максимальное значение уставки пола
    27: ("lowerLimit", 1),  # в °C, минимальное значение уставки пола
    28: ("maxSchedulePeriod", 2),  # максимальное число периодов расписания в сутки
    29: ("tempTemperature", 2),  # в °C, температура временного режима
    33: ("upperAirLimit", 1),  # в °C, максимальное значение уставки воздуха
    34: ("lowerAirLimit", 1),  # в °C, минимальное значение уставки воздуха
    35: ("upperU", 4),  # в вольтах, верхний порог срабатывания по напряжению
    36: ("lowerU", 2),  # в вольтах, нижний порог срабатывания по напряжению
    37: ("upperP", 2),  # в 100 ватт, порог срабатывания по мощности
    38: ("upperI", 4),  # в 1/10 ампера, верхний порог срабатывания по току
    39: ("middleI", 4),  # в 1/10 ампера, средний порог срабатывания по току
    40: ("lowerI", 4),  # в 1/10 ампера, нижний порог срабатывания по току
    41: ("tOnDelay", 4),  # в секундах, задержка на включение реле
    42: ("tOffDelay", 2),
    # в секундах, задержка на выключение реле при превышении верхнего предела по току или мощности
    43: ("middleITime", 2),  # в 1/10 секунды, задержка на выключение реле при превышении среднего предела тока
    44: ("lowerITime", 2),  # в 1/10 секунды, задержка на выключение реле при токе ниже нижнего предела
    45: ("lowVoltageTime", 4),  # в 1/10 секунды, длительность провала напряжения
    46: ("correctionsU", 1),  # в вольтах, поправка вольтметра
    47: ("correctionsI", 1),  # в процентах, поправка амперметра
    48: ("repTimes", 2),  # количество отлючений реле по току или напряжению до блокировки устройства
    49: ("powerType", 2),  # тип контролируемой мощности: активная(Вт)=0, реактивная(ВАР)=1, полная(ВА)=2
    50: ("showType", 2),
    # тип отображаемого параметра: ток=0, акт. мощн.=1, реакт. мощн.=2, полная мощн.=3, косинус фи=4
    51: ("sensorСontrolNumber", 2),  # номер удалённого датчика для контроля температуры
    112: ("proMode", 7),  # профессиональная модель задержки на выключение по напряжению
    113: ("voltageStableDelay", 7),  # задержка на включение реле считает с момента нормализации напряжения
    114: ("androidBlock", 7),  # блокировка любых изменений настроек через offlineApi
    115: ("cloudBlock", 7),  # блокировка любых изменений настроек и перепрошивки через облако
    116: ("useContactorControl", 7),  # нагрузка через контактор (только учёт электроэнергии)
    117: ("NCContactControl", 7),  # инвертированное реле
    118: ("coolingControlWay", 7),  # режим нагрев/охлаждения
    121: ("preControl", 7),  # предварительный нагрев
    122: ("windowOpenControl", 7),  # режим открытого окна
    124: ("childrenLock", 7),  # защита от детей
    125: ("powerOff", 7)  # выключение
}

terneo_params_rev_map = {v[0]: (k, v[1]) for k, v in terneo_params_map.items()}

terneo_telemetry_map = {
    "t.0": ("internalOverheatSensor", 16),
    "t.1": ("floorSensor", 16),
    "t.2": ("airSensor", 16),
    "t.3": ("precipitationSensor", 16),
    "t.4": ("externalObject", 16),
    "t.5": ("currentSetting", 16),
    "t.6": ("correction", 16),

    "u.0": ("maximumVoltage", None),
    "u.1": ("minimumVoltage", None),
    "u.2": ("supplyVoltage", 100),
    "u.3": ("batteryVoltage", 10),
    "u.4": ("upperThreshold", None),
    "u.5": ("lowerThreshold", None),
    "u.6": ("mediumVoltage", None),

    "i.0": ("maximumCurrent", 10),
    "i.1": ("averageCurrent", 10),
    "i.2": ("minimumCurrent", 10),
    "i.3": ("upperCurrentLimit", 10),
    "i.4": ("averageCurrentLimit", 10),
    "i.5": ("lowerCurrentLimit", 10),

    "w.0": ("upperPowerLimit", None),
    "w.1": ("maximumLoadPower", None),
    "w.2": ("averageLoadPower", None),
    "w.3": ("minimumLoadPower", None),
    "w.4": ("maxCosinePhi", 100),
    "w.5": ("avgCosinePhi", 100),
    "w.6": ("minCosinePhi", 100),

    "r.0": ("soilMoistureSensor", None),

    "p.0": ("maxActiveLoadPower", None),
    "p.1": ("avgActiveLoadPower", None),
    "p.2": ("minActiveLoadPower", None),
    "p.3": ("maxReactiveLoadPower", None),
    "p.4": ("avgReactiveLoadPower", None),
    "p.5": ("minReactiveLoadPower", None),

    "m.0": ("typeOfControl", None),  # пол = 0, воздух = 1, расширенный = 2
    "m.1": ("typeOfManagement", None),  # по расписанию = 0, ручной = 3, отъезд = 4, временный = 5
    "m.2": ("numberPeriodOfSchedule", None),  # первый период понедельника = 0, вторника = maxSchedulePeriod…
    "m.3": ("lockType", None),
    # нет блокировок = 0, блокировка изменений из облака = 1, блокировка изменений из локальной сети = 2, обе = 3
    "m.4": ("typeOfControlledPower", None),  # активная мощность = 0, реактивная мощность = 1, полная мощность = 2

    "o.0": ("wifiSignalLevel", None),
    "o.1": ("lastReboot", None),
    # выключение питания = 0x04, програмный сброс = 0x08, сторожевой таймер = 0x10, низкое напряжение = 0x40
    "f.0": ("loadCondition", None),
    "f.1": ("waitingForLoad", None),
    "f.2": ("actionOnTheFloorLimit", None),
    "f.3": ("floorSensorBreak", None),
    "f.4": ("floorSensorShortCircuit", None),
    "f.5": ("airSensorBreak", None),
    "f.6": ("airSensorShortCircuit", None),
    "f.7": ("preheatingAction", None),
    "f.8": ("openWindowAction", None),
    "f.9": ("internalOverheating", None),
    "f.10": ("batteryLow", None),
    "f.11": ("clockProblem", None),
    "f.12": ("noOverheatingControl", None),
    "f.13": ("proportionalLoadOperation", None),
    "f.14": ("digitalFloorSensor", None),
    "f.15": ("watchdogReboot", None),
}

terneo_telemetry_rev_map = {v[0]: (k, v[1]) for k, v in terneo_telemetry_map.items()}


class TerneoAX:
    GET_PARAMS = {"cmd": 1}
    GET_SCHEDULE = {"cmd": 2}
    GET_TELEMETRY = {"cmd": 4}

    MODE_OFF = 'OFF'
    MODE_SCHEDULE = 'schedule'
    MODE_HEAT = 'heat'
    STATE_IDLE = 'idle'
    STATE_HEATING = 'heating'
    STATE_UNKNOWN = 'unknown'
    TYPE_INT = 1
    TYPE_STR = 0

    def __init__(self, addr, timeout=5, name=None):
        self.log = logging.getLogger(__name__)

        self.addr = addr
        self.timeout = timeout
        self._name = name

        self._sn = None
        self._params = None
        self._telemetry = None
        self._schedule = None
        self.last_update_params = 0

    @property
    def name(self):
        if self._name is not None:
            return self._name
        else:
            return self._sn[0:5]

    def _request(self, path, data=None):
        uri = "http://{addr}/{path}".format(addr=self.addr, path=path)
        try:
            if data is not None:
                req = requests.post(uri,
                                    timeout=(self.timeout / 2, self.timeout),
                                    data=json.dumps(data)
                                    )
            else:
                req = requests.get(uri,
                                   timeout=(self.timeout / 2, self.timeout),
                                   )
        except Exception as ex:
            self.log.error(
                "Error requesting {uri} from Terneo AX. {data} {err}".format(uri=uri, err=str(ex), data=str(data)))
            return False

        if not req.ok:
            self.log.error("Connection error logging into Terneo AX. Status Code: {status}".format(
                status=req.status_code))
            return False

        return req

    def send_changed_params(self) -> bool:
        if self._params is None:
            return False
        param: TerneoParam
        updates = []
        for key, param in self._params.items():
            if param.readValue != param.setValue:
                k, _ = terneo_params_rev_map.get(key, (None, None))
                if k is not None:
                    updates.append([k,
                                    param.type,
                                    str(param.setValue)])
                else:
                    self.log.error("error: key:{} not found in reverse map".format(key))
        if len(updates):
            self.log.info("{} updates: {}".format(self.addr, str(updates)))
            data = {
                "sn": self._sn,
                "par": updates
            }
            r = self._request("api.cgi", data)
            if r is False:
                return False

            try:
                data = r.json()
            except json.decoder.JSONDecodeError as ex:
                self.log.error("Json error: {err}".format(err=str(ex)))
                return False
            self.log.info("{} Response: {}".format(self.addr, str(data)))
            return True
        else:
            return False

    def update_params(self):

        if not self.send_changed_params() and (time() - self.last_update_params < 60):
            return True

        r = self._request("api.cgi", self.GET_PARAMS)

        if r is False:
            return False

        try:
            data = r.json()
        except json.decoder.JSONDecodeError as ex:
            self.log.error("Json error: {err}".format(err=str(ex)))
            return False

        self._sn = data.get("sn", None)
        params = data.get("par", [])

        if self._params is None:
            self._params = {}

        for param in params:
            key, _ = terneo_params_map.get(param[0], (None, None))
            if key is not None:
                if param[1] in [1, 2, 3, 4, 5, 6, 7]:  # type 0-string 1..7 int, unsigned int and bool
                    param_value = int(param[2])
                else:
                    param_value = param[2]
                param_type = param[1]

                if key in self._params:
                    tmp: TerneoParam = self._params[key]
                    self._params[key] = tmp._replace(readValue=param_value)
                else:
                    self._params[key] = TerneoParam(param_value, param_value, param_type, 0)

        self.last_update_params = time()
        return True

    def update_telemetry(self):
        r = self._request("api.cgi", self.GET_TELEMETRY)

        if r is False:
            return r
        try:
            data = r.json()
        except json.decoder.JSONDecodeError as ex:
            self.log.error("Json error: {err}".format(err=str(ex)))
            return False
        self._sn = data.get("sn", None)
        self._telemetry = {}
        for k, v in data.items():
            key = terneo_telemetry_map.get(k, None)
            if key is not None:
                self._telemetry[key[0]] = int(v) if key[1] is None else int(v) / key[1]

        return True

    def update_schedule(self):
        r = self._request("api.cgi", self.GET_SCHEDULE)

        if r is False:
            return r
        data = r.json()
        self._sn = data.get("sn", None)
        self._schedule = data.get("tt", None)

        return True

    def get_param(self, attr):
        if self._params is not None:
            param: TerneoParam = self._params.get(attr, None)
            if param is not None:
                # self.log.info("get param {} {} {}".format(self.addr, attr, param.setValue))
                return param.setValue

    def set_param(self, attr, value) -> bool:
        # self.log.info("set param {} {} {}".format(self.addr, attr, value))
        if self._params is not None:
            param: TerneoParam = self._params.get(attr, None)
            if param is None:
                _, type_attr = terneo_params_rev_map.get(attr, (None, None))
                param = TerneoParam(None, None, type_attr, None)
            self._params[attr] = param._replace(setValue=value)
            return True
        else:
            return False

    def get_telemetry(self, attr):
        if self._telemetry is not None:
            return self._telemetry.get(attr, None)

    def get_current_temp(self):
        return self.get_telemetry('floorSensor')

    def get_upper_temp_limit(self):
        return self.get_param('upperLimit')

    def get_lower_temp_limit(self):
        return self.get_param('lowerLimit')

    @property
    def heattemp(self):
        return self.get_temp_setting()

    def get_temp_setting(self):
        if self.away:
            return self.get_param('awayFloorTemperature')
        else:
            return self.get_param('manualFloorTemperature')

    def set_temp_setting(self, temp) -> bool:
        if self.away:
            return self.set_param('awayFloorTemperature', temp)
        else:
            return self.set_param('manualFloorTemperature', temp)

    @property
    def mode(self):
        return self.get_current_mode()

    def set_mode(self, mode):
        self.log.info("Set mode: {}".format(mode))
        if mode == self.MODE_OFF:
            self.set_param('powerOff', 1)
        elif mode == self.MODE_HEAT:
            self.set_param('powerOff', 0)
            self.set_param('mode', 1)
        elif mode == self.MODE_SCHEDULE:
            self.set_param('powerOff', 0)
            self.set_param('mode', 0)
        else:
            return False
        return True

    def get_current_mode(self):
        # OFF, HEAT, SCHEDULE, UNKNOWN
        if self.get_param('powerOff') == 1:
            return self.MODE_OFF
        elif self.get_param('mode') == 0:
            return self.MODE_SCHEDULE
        elif self.get_param('mode') == 1:
            return self.MODE_HEAT
        else:
            return 'UNKNOWN'

    @property
    def state(self):
        return self.get_current_state()

    def get_current_state(self):
        # IDLE HEATING UNKNOWN
        cond = self.get_telemetry('loadCondition')
        if cond == 0:
            return self.STATE_IDLE
        elif cond == 1:
            return self.STATE_HEATING
        return self.STATE_UNKNOWN

    @property
    def away(self) -> bool:
        return self._is_away_mode_now()

    def set_home(self) -> bool:
        self.set_param('startAwayTime', 536112000)
        self.set_param('endAwayTime', 536112000)
        return True

    def set_away(self, away_time: int) -> bool:
        beginTime = datetime.datetime.strptime("2000:01:01 00:00:00", "%Y:%m:%d %H:%M:%S").timestamp()
        nowTime = int(time() - beginTime)
        startAway = nowTime - 10
        endAway = nowTime + away_time
        self.set_param('startAwayTime', startAway)
        self.set_param('endAwayTime', endAway)
        return True

    @property
    def schedule(self):
        return 0

    def is_local_lan_remote_control_enabled(self) -> bool:
        flag = self.get_telemetry('lockType')
        # self.log.info("Remote control {} {}".format(self.addr, flag))
        if flag is not None:
            return (flag & 2) == 0
        return True

    def _is_away_mode_now(self):
        startAway = self.get_param('startAwayTime')
        endAway = self.get_param('endAwayTime')
        beginTime = datetime.datetime.strptime("2000:01:01 00:00:00", "%Y:%m:%d %H:%M:%S").timestamp()
        nowTime = int(time() - beginTime)
        if startAway is not None and endAway is not None:
            return startAway < nowTime and nowTime < endAway
        return False
