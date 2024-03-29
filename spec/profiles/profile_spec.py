from enerdata.profiles.profile import *
from enerdata.contracts.tariff import T20DHA, T30A
from enerdata.metering.measure import *



with description("A coeficient"):
    with before.all:
        start = TIMEZONE.localize(datetime(2014, 1, 1))
        end = TIMEZONE.localize(datetime(2015, 1, 1))
        cofs = []
        day = start
        while day < end:
            day += timedelta(hours=1)
            cofs.append((TIMEZONE.normalize(day), {'A': 0, 'B': 0}))
        self.cofs = cofs

    with it("must read and sum the hours of the file"):
        # TODO: Move this test to integration test with REE
        cofs = REEProfile.get(2014, 10)
        # We have one hour more in October
        assert len(cofs) == (31 * 24) + 1
        # The first second hour in the 26th of October is DST
        assert cofs[(24 * 25) + 1][0].dst() == timedelta(seconds=3600)
        # The second second hour in the 26th of October is not DST
        assert cofs[(24 * 25) + 2][0].dst() == timedelta(0)
        assert REEProfile._CACHE['201410'] == cofs


    with it("must return the sum of coefs for each period"):
        c = Coefficients(self.cofs)
        t = T20DHA()
        t.cof = 'A'
        assert c.get_coefs_by_tariff(t, date(2014, 1, 1), date(2014, 1, 31)) == {'P1': 0, 'P2': 0}


    with it('should insert coeficients if empty'):
        c = Coefficients()
        assert len(c.coefs) == 0
        c.insert_coefs(self.cofs)
        assert len(c.coefs) == (365 * 24)

    with it('should replace the coeficients'):
        c = Coefficients(self.cofs)
        assert len(c.coefs) == (365 * 24)
        c.insert_coefs(self.cofs)
        assert len(c.coefs) == (365 * 24)

    with it('should append the coefficients'):
        c = Coefficients()
        c.insert_coefs(self.cofs)
        start = TIMEZONE.localize(datetime(2015, 1, 1))
        end = TIMEZONE.localize(datetime(2015, 2, 1))
        cofs = []
        day = start
        while day < end:
            cofs.append((TIMEZONE.normalize(day + timedelta(hours=1)), {'A': 0, 'B': 0}))
            day += timedelta(hours=1)
        c.insert_coefs(cofs)
        assert c.coefs[0][0] == TIMEZONE.localize(datetime(2014, 1, 1, 1))
        assert c.coefs[-1][0] == TIMEZONE.localize(datetime(2015, 2, 1))
        assert len(c.coefs) == ((365 * 24) + (31 * 24))

    with it('should return the range of dates'):
        c = Coefficients(self.cofs)
        cofs = c.get_range(date(2014, 10, 26), date(2014, 10, 26))
        assert len(cofs) == 25
        assert cofs[1][0] == TIMEZONE.localize(datetime(2014, 10, 26, 2), is_dst=True)
        assert cofs[2][0] == TIMEZONE.localize(datetime(2014, 10, 26, 2), is_dst=False)

        cofs = c.get_range(date(2014, 3, 30), date(2014, 3, 30))
        assert len(cofs) == 23
        assert cofs[1][0] == TIMEZONE.normalize(TIMEZONE.localize(datetime(2014, 3, 30, 2)))


with description("When profiling"):

    with it('the total energy must be the sum of the profiled energy'):
        c = Coefficients(REEProfile.get(2014, 10))
        profiler = Profiler(c)
        measures = [
            EnergyMeasure(
                date(2014, 9, 30),
                TariffPeriod('P1', 'te'), 307, consumption=145
            ),
            EnergyMeasure(
                date(2014, 9, 30),
                TariffPeriod('P2', 'te'), 108, consumption=10
            ),
            EnergyMeasure(
                date(2014, 10, 31),
                TariffPeriod('P1', 'te'), 540, consumption=233
            ),
            EnergyMeasure(
                date(2014, 10, 31),
                TariffPeriod('P2', 'te'), 150, consumption=42
            )
        ]
        t = T20DHA()
        t.cof = 'A'
        prof = list(profiler.profile(t, measures))
        assert len(prof) == (31 * 24) + 1
        consum = sum([i[1]['aprox'] for i in prof])
        assert consum == 233 + 42

    with it('should be the same per period if drag per period is used'):
        c = Coefficients()
        c.insert_coefs(REEProfile.get(2015, 2))
        c.insert_coefs(REEProfile.get(2015, 3))
        profiler = Profiler(c)
        measures = [
            EnergyMeasure(
                date(2015, 2, 17),
                TariffPeriod('P1', 'te'), 0, consumption=0
            ),
            EnergyMeasure(
                date(2015, 2, 17),
                TariffPeriod('P2', 'te'), 0, consumption=0
            ),
            EnergyMeasure(
                date(2015, 2, 17),
                TariffPeriod('P3', 'te'), 0, consumption=0
            ),
            EnergyMeasure(
                date(2015, 2, 17),
                TariffPeriod('P4', 'te'), 0, consumption=0
            ),
            EnergyMeasure(
                date(2015, 2, 17),
                TariffPeriod('P5', 'te'), 0, consumption=0
            ),
            EnergyMeasure(
                date(2015, 2, 17),
                TariffPeriod('P6', 'te'), 0, consumption=0
            ),
            EnergyMeasure(
                date(2015, 3, 18),
                TariffPeriod('P1', 'te'), 0, consumption=282
            ),
            EnergyMeasure(
                date(2015, 3, 18),
                TariffPeriod('P2', 'te'), 0, consumption=156
            ),
            EnergyMeasure(
                date(2015, 3, 18),
                TariffPeriod('P3', 'te'), 0, consumption=325
            ),
            EnergyMeasure(
                date(2015, 3, 18),
                TariffPeriod('P4', 'te'), 0, consumption=56
            ),
            EnergyMeasure(
                date(2015, 3, 18),
                TariffPeriod('P5', 'te'), 0, consumption=643
            ),
            EnergyMeasure(
                date(2015, 3, 18),
                TariffPeriod('P6', 'te'), 0, consumption=32
            )
        ]
        t = T30A()
        t.cof = 'C'
        prof = list(profiler.profile(t, measures, drag_method='period'))
        cons = {}
        for p in prof:
            period = p[1]['period']
            cons.setdefault(period, 0)
            cons[period] += p[1]['aprox']

        assert cons['P1'] == 282
        assert cons['P2'] == 156
        assert cons['P3'] == 325
        assert cons['P4'] == 56
        assert cons['P5'] == 643
        assert cons['P6'] == 32
