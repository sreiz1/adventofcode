# privaterank - allows ranking your advent of code scores against others in private leaderboards,
# even if you've done them after the fact, so as to allow realistic practise with past exercises.
# this depends on your adding certain headers to your solutions in jupyter notebook files,
# one of which is the starting timestamp. obviously this depends
# on your own honor - if you start working on a puzzle first (or even read about it), and then afterwards
# add the timestamp the result will be skewed. so - this is only for personal use, and not meant to
# publish the results anywhere or brag about them. NB if other people in the leaderboard also started late this
# tool won't recognize it, and you may gain false confidence. for now only headers in jupyter notebook files 
# are processed, but it would be pretty easy to add support for other langauges and formats.
# the needed headers are, for example:
# 2019 day 2
# start_ts=1643360000
# then after you've completed that assignment, you'll have to save the json file of a private leaderboard ranking
# with your solution ranked in it (probably low because you completed it late, the file can be saved from
# private leaderboard - API - JSON), 
# usage: python privaterank.py 'Own Name' leaderboard.json

import json
import glob
import sys
import datetime
import pytz
import tabulate

def notebook2yds(filename):
    '''read a notebook file, then extract and return a list of (year, daynum, start_ts) from it'''
    res=[]
    with open(filename) as f:
        jsn=json.load(f)
        for cell in jsn['cells']:
            if cell['cell_type']!='code':
                continue
            src=cell['source']
            assert isinstance(src, list)
            year=None
            day=None
            start_ts=None
            try:
                for line in src:
                    if line.startswith('# 20'):
                        parts=line.split()
                        if parts[0]=='#' and parts[2]=='day':
                            year=int(parts[1])
                            day=int(parts[3])
                    elif line.startswith('# start_ts='):
                        start_ts=int(line[len('# start_ts='):])
            except ValueError:
                continue
            if not (year is None or day is None or start_ts is None):
                res.append( (year, day, start_ts) )
    return res

def get_timestamps(own_name, total_yds, inputfile):
    '''read an aoc leaderboard json file, and from that deduce the names
    of contestants and their supposed starting times for each exercise, and recorded completion times per star.
    this data is combined with own_name and total_yds for yourself.
    returns a map of (day num, name) to a map with start, star1, star2 fields'''
    aoc=None
    with open(inputfile) as f:
        aoc=json.load(f)
    year=int(aoc['event'])
    total_yds=[ tup for tup in total_yds if tup[0]==year ]
    res={}
    for member in aoc['members'].values():
        name=member['name']
        for daynum0, stardata in member['completion_day_level'].items():
            if len(stardata)<1:
                continue
            daynum=int(daynum0)
            start_ts=datetime.datetime(year, 12, daynum, hour=0, tzinfo=pytz.timezone('US/Eastern')).timestamp()
            if name==own_name:
                for tup in total_yds:
                    if tup[1]==daynum:
                        start_ts=tup[2]
                        break
            key=(daynum, name)
            dd=res.setdefault(key, {})
            dd['start']=start_ts
            if '1' in stardata:
                dd['star1']=stardata['1']['get_star_ts']
            if '2' in stardata:
                dd['star2']=stardata['2']['get_star_ts']
    return res, year

def show_report(own_name, data, year):
    '''for each day where you competed show the ranking up until yourself, ranked by points'''
    own_name_enc=own_name.encode('ascii')
    for daynum0 in range(25):
        daynum=daynum0+1
        if (daynum, own_name) not in data:
            continue
        print(f'Ranking for day {daynum} of {year}:')
        repdata=[]
        for key, tsdata in data.items():
            if key[0]!=daynum:
                continue
            name=key[1].encode('ascii', errors='ignore') if key[1] else '?'
            star1min=(tsdata['star1']-tsdata['start'])/60.0 if 'star1' in tsdata else None
            star2min=(tsdata['star2']-tsdata['start'])/60.0 if 'star2' in tsdata else None
            repdata.append([name, star1min, star2min, 0])
        for score_index in [1,2]:
            repdata.sort(key=lambda reptup: 1.0e10 if reptup[score_index] is None else reptup[score_index])
            for i,reptup in enumerate(repdata):
                if reptup[score_index] is not None:
                    reptup[-1]+=len(repdata)-i
        repdata.sort(key=lambda reptup: -reptup[-1])
        # now truncate somewhere below own position to avoid making the list too long
        for i in range(len(repdata)):
            reptup=repdata[i]
            if reptup[0]==own_name_enc:
                repdata=repdata[:i+6]
                break
        report=tabulate.tabulate(repdata, floatfmt='.1f', tablefmt='text',
         headers=['Name', 'First * (min.)', 'Second * (min.)', 'Score'])
        print(report)
        print()

def main(own_name, inputfile):
    notebooks=glob.glob('*.ipynb')
    total_yds=[]
    for n in notebooks:
        list_yds=notebook2yds(n)
        total_yds.extend(list_yds)
    data, year=get_timestamps(own_name, total_yds, inputfile)
    show_report(own_name, data, year)

if __name__ == '__main__':
    if len(sys.argv)<3:
        raise ValueError("usage: python privaterank.py 'Own Name' leaderboard.json")
    main(*sys.argv[1:])
