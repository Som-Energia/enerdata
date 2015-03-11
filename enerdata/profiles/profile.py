import bisect
from datetime import datetime, date, timedelta
from multiprocessing import Lock
from StringIO import StringIO

from enerdata.datetime.timezone import TIMEZONE
from enerdata.metering.measure import Measure


class Coefficients(object):

    def __init__(self, coefs=None):
        if coefs is None:
            coefs = []
        assert isinstance(coefs, list)
        self.coefs = list(coefs)

    def insert_coefs(self, coefs):
        pos_0 = bisect.bisect_left(self.coefs, coefs[0])
        pos_1 = bisect.bisect_right(self.coefs, coefs[-1])
        del self.coefs[pos_0:pos_1]
        self.coefs.extend(coefs)

    def get_range(self, start, end):
        assert isinstance(start, date)
        assert isinstance(end, date)
        start = TIMEZONE.localize(datetime(
            start.year, start.month, start.day, 1), is_dst=True
        )
        # Sum one day to get the hour 00:00 of the next day
        end += timedelta(days=1)
        end = TIMEZONE.localize(datetime(
            end.year, end.month, end.day), is_dst=True
        ) + timedelta(seconds=1)
        pos = bisect.bisect_left(self.coefs, (start, {}))
        if pos == len(self.coefs):
            raise ValueError('start date not found in coefficients')
        end_pos = bisect.bisect_right(self.coefs, (end, {}))
        return self.coefs[pos:end_pos]

    def get_coefs_by_tariff(self, tariff, start, end):
        assert hasattr(tariff, 'get_period_by_date')
        assert hasattr(tariff, 'energy_periods')
        assert isinstance(start, date)
        assert isinstance(end, date)
        holidays = []
        sum_cofs = dict.fromkeys(tariff.energy_periods.keys(), 0)
        for hour, coef in self.get_range(start, end):
            if len(sum_cofs) > 1:
                period = tariff.get_period_by_date(hour, holidays)
                p_name = period.code
            else:
                p_name = sum_cofs.keys()[0]
            sum_cofs[p_name] += coef[tariff.cof]
        return sum_cofs


class Profiler(object):

    def __init__(self, coefficient):
        self.coefficient = coefficient

    def profile(self, tariff, measures):
        #{'PX': [(date(XXXX-XX-XX), 100), (date(XXXX-XX-XX), 110)]}
        _measures = list(measures)
        measures = {}
        for m in sorted(_measures):
            measures.setdefault(m.period.code, [])
            measures[m.period.code].append(m)
        start, end = measures.values()[0][0].date, measures.values()[0][-1].date
        sum_cofs = self.coefficient.get_coefs_by_tariff(tariff, start, end)
        drag = 0
        for hour, cof in self.coefficient.get_range(start, end):
            # TODO: Implement holidays
            period = tariff.get_period_by_date(hour)
            d = hour.date()
            if hour.hour == 0:
                d -= timedelta(days=1)
            fake_m = Measure(d, period, 0)
            pos = bisect.bisect_left(measures[period.code], fake_m)
            consumption = measures[period.code][pos].consumption
            cof = cof[tariff.cof]
            hour_c = ((consumption * cof) / sum_cofs[period.code]) + drag
            aprox = round(hour_c)
            drag = hour_c - aprox
            yield (
                hour,
                {
                    'aprox': aprox,
                    'drag': drag,
                    'consumption': consumption,
                    'consumption_date': measures[period.code][pos].date,
                    'sum_cofs': sum_cofs[period.code],
                    'cof': cof
                }
            )


class REEProfile(object):

    HOST = 'www.ree.es'
    PATH = '/sites/default/files/simel/perff'
    down_lock = Lock()

    _CACHE = {}

    @classmethod
    def get(cls, year, month):
        try:
            cls.down_lock.acquire()
            import csv
            import httplib
            key = '%(year)s%(month)02i' % locals()
            conn = None
            if key in cls._CACHE:
                return cls._CACHE[key]
            perff_file = 'PERFF_%(key)s.gz' % locals()
            conn = httplib.HTTPConnection(cls.HOST)
            conn.request('GET', '%s/%s' % (cls.PATH, perff_file))
            r = conn.getresponse()
            if r.msg.type == 'application/x-gzip':
                import gzip
                c = StringIO(r.read())
                m = StringIO(gzip.GzipFile(fileobj=c).read())
                c.close()
                reader = csv.reader(m, delimiter=';')
                header = True
                cofs = []
                for vals in reader:
                    if header:
                        header = False
                        continue
                    if int(vals[3]) == 1:
                        n_hour = 1
                    dt = datetime(
                        int(vals[0]), int(vals[1]), int(vals[2])
                    )
                    day = TIMEZONE.localize(dt, is_dst=bool(not int(vals[4])))
                    day += timedelta(hours=n_hour)
                    n_hour += 1
                    cofs.append(
                        (TIMEZONE.normalize(day), dict(
                            (k, float(vals[i])) for i, k in enumerate('ABCD', 5)
                        ))
                    )
                cls._CACHE[key] = cofs
                return cofs
            else:
                raise Exception('Profiles from REE not found')
        finally:
            if conn is not None:
                conn.close()
            cls.down_lock.release()
