#! /usr/bin/python

import os.path
import sys
sys.path.append('/data/project/pb/pb/web/dynamic/')

import pb_db_config
sys.path.append(os.path.abspath(pb_db_config.base_path + '../pyapi'))

import wppb
db = wppb.Database(database=pb_db_config.db_name)

(months, year_months) = db.get_months()
(counts_cf, sums_cf, totals_cf) = db.get_stats(year_months, db.get_confirmations_by_month())
(counts_u, sums_u, totals_u) = db.get_stats(year_months, db.get_users_by_month())

data = {'months': months, 'year_months': year_months, 'confirmations': {'counts': counts_cf, 'sums': sums_cf, 'totals': totals_cf}, 'users': {'counts': counts_u, 'sums': sums_u, 'totals': totals_u}}

import pickle
pickle.dump(data, open('/data/project/pb/stats.pickle', 'w'))
