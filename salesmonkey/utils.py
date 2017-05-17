from datetime import datetime
import random

from hashlib import md5


class OrderNumberGenerator:
    def generate(self, aCart):
        monkey_species = ['BABOON', 'MONKEY', 'APE', 'GORILLA', 'CAPUCHIN', 'TAMARIN', 'GIBBON']
        specie = random.choice(monkey_species)

        num = 'WEB{0}-{1}-{2}'.format(specie,
                                      datetime.strftime(datetime.now(), '%Y%m%d'),
                                      str(abs(42+hash(datetime.now())))[:4])
        return num
