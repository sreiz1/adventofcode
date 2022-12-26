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
# usage: python privaterank.py [-ownonly] 'Own Name' leaderboard.json...
# * You can specify multiple leaderboard json files of a certain year to calculate a combined leaderboard
# * Adding the -ownonly option will only show a list of your own times
# * The default is to show a ranking per day (up to 5 places below your own) and total, based on points
# * For single leaderboard files the points should match the ones reported by the AOC web site

import json
import glob
import sys
import datetime
import pytz
import tabulate
import collections

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

def get_timestamps(own_name, total_yds, inputfile, res=None, year=None, multiboard=False):
    '''read an aoc leaderboard json file, and from that deduce the names
    of contestants and their supposed starting times for each exercise, and recorded completion times per star.
    this data is combined with own_name and total_yds for yourself.
    returns a map of (day num, id) to a map with start, star1, star2, star1index, star2index, name fields'''
    aoc=None
    with open(inputfile) as f:
        aoc=json.load(f)
    year1=int(aoc['event'])
    if year is None:
        year=year1
    else:
        assert year==year1
    if res is None:
        res={}
    for member in aoc['members'].values():
        name=member['name']
        id=int(member['id'])
        for daynum0, stardata in member['completion_day_level'].items():
            daynum=int(daynum0)
            assert 1<=daynum<=25
            start_ts=datetime.datetime(year, 12, daynum, hour=0, tzinfo=pytz.timezone('US/Eastern')).timestamp()
            key=(daynum, id)
            dd=res.setdefault(key, {})
            dd['start']=start_ts
            dd['name']=name
            for si in ['1', '2']:
                if si in stardata:
                    dd[f'star{si}']=stardata[si]['get_star_ts']
                    dd[f'star{si}index']=stardata[si]['star_index']
                    if multiboard: # star index is per board so won't work, use less accurate timestamps
                        dd[f'star{si}index']=stardata[si]['get_star_ts']
    patch_data(res, own_name, total_yds, year)
    all_ids={ key[1] for key in res.keys() }
    num_participants=max(len(all_ids), len(aoc['members']))
    return res, year, num_participants

def patch_data(data, own_name, total_yds, year):
    '''patch own data based on explicit timestamps'''
    total_yds=[ tup for tup in total_yds if tup[0]==year ]
    for daynum in range(1, 26):
        repdata=[]
        daypatched=False
        for key, tsdata in data.items():
            if key[0]!=daynum:
                continue
            id=key[1]
            name=tsdata['name']
            name_enc=None
            start_ts=tsdata['start']
            if name==own_name:
                for tup in total_yds:
                    if tup[1]==daynum:
                        start_ts=tup[2]
                        tsdata['start']=start_ts
                        daypatched=True
                        break
            star1min=(tsdata['star1']-start_ts)/60.0 if 'star1' in tsdata else None
            star2min=(tsdata['star2']-start_ts)/60.0 if 'star2' in tsdata else None
            repdata.append([(id,name), name_enc, star1min, star2min, tsdata.get('star1index', sys.maxsize), \
             tsdata.get('star2index', sys.maxsize)])
        if not daypatched:
            continue
        for si in ['1', '2']:
            # sort on timestamp of the star
            score_index=int(si)+1
            repdata.sort(key=lambda reptup: 1.0e10 if reptup[score_index] is None else reptup[score_index])
            # find our own entry and depending on neighbours find a fake starindex that fits
            pos=None
            for i,reptup in enumerate(repdata):
                if reptup[0][1]==own_name:
                    pos=i
                    break
            assert pos is not None
            if repdata[pos][score_index] is None:
                continue
            if pos==0:
                if repdata[pos][score_index+2]<repdata[pos+1][score_index+2]:
                    continue
                starindex=repdata[pos+1][score_index+2]-1
            elif pos==len(repdata)-1:
                if repdata[pos][score_index+2]>repdata[pos-1][score_index+2]:
                    continue
                starindex=repdata[pos-1][score_index+2]+1
            else:
                assert 1<=pos<=len(repdata)-2
                sind1=repdata[pos-1][score_index+2]
                sind2=repdata[pos+1][score_index+2]
                if sind1<repdata[pos][score_index+2]<sind2:
                    continue
                assert sind2>sind1
                starindex=(sind1+sind2)/2
            # patch
            id=repdata[pos][0][0]
            key=(daynum, id)
            dd=data.setdefault(key, {})
            dd[f'star{si}index']=starindex
        print(f'patched own data for day {daynum}')

def check_data(data, num_participants):
    for daynum in range(1, 26):
        repdata=[]
        for key, tsdata in data.items():
            if key[0]!=daynum:
                continue
            id=key[1]
            name=tsdata['name']
            name_enc=None
            star1min=(tsdata['star1']-tsdata['start'])/60.0 if 'star1' in tsdata else None
            star2min=(tsdata['star2']-tsdata['start'])/60.0 if 'star2' in tsdata else None
            repdata.append([(id,name), name_enc, star1min, star2min, tsdata.get('star1index', sys.maxsize), \
                tsdata.get('star2index', sys.maxsize), 0])
        assert num_participants>=len(repdata)
        for score_index in [4, 5]: # assign points per star based on ranking
            repdata.sort(key=lambda reptup: reptup[score_index])
            for i,reptup in enumerate(repdata):
                if reptup[score_index]!=sys.maxsize:
                    reptup[-1]+=num_participants-i
                assert (reptup[3] is None) or (reptup[2]<=reptup[3])
                assert (reptup[5]==sys.maxsize) or (reptup[4]<reptup[5])
                if i<len(repdata)-1:
                    reptup2=repdata[i+1]
                    if not ((reptup2[score_index-2] is None) or (reptup[score_index-2]<=reptup2[score_index-2])):
                        print('failed 1', reptup)
                        print('failed 2', reptup2)
                    assert (reptup2[score_index-2] is None) or (reptup[score_index-2]<=reptup2[score_index-2])
                if reptup[score_index] is not None:
                    reptup[-1]+=num_participants-i
        #print(f'day {daynum}: checked {len(repdata)} entries')
    #print(f'{num_participants=}')

def encode_name(name, id):
    '''to strip out non-ascii chars we encode to ascii and back'''
    return name.encode('ascii', errors='ignore').decode('ascii') if name else f'(anonymous user #{id})'

def show_report(own_name, data, year, num_participants):
    '''for each day where you competed show the ranking up until yourself, ranked by points,
    also calculates and returns total points per participant'''
    total_points=collections.Counter() # maps (id,name) to total points
    for daynum in range(1, 26):
        repdata=[]
        for key, tsdata in data.items():
            if key[0]!=daynum:
                continue
            id=key[1]
            name=tsdata['name']
            name_enc=encode_name(name, id)
            star1min=(tsdata['star1']-tsdata['start'])/60.0 if 'star1' in tsdata else None
            star2min=(tsdata['star2']-tsdata['start'])/60.0 if 'star2' in tsdata else None
            repdata.append([(id,name), name_enc, star1min, star2min, tsdata.get('star1index', sys.maxsize), \
             tsdata.get('star2index', sys.maxsize), 0])
        assert num_participants>=len(repdata)
        for score_index in [4, 5]: # assign points per star based on ranking
            repdata.sort(key=lambda reptup: reptup[score_index])
            for i,reptup in enumerate(repdata):
                if reptup[score_index]!=sys.maxsize:
                    reptup[-1]+=num_participants-i
        repdata.sort(key=lambda reptup: -reptup[-1])
        for reptup in repdata:
            total_points[reptup[0]]+=reptup[-1]
        # truncate somewhere below own position to avoid making the list too long
        for i,reptup in enumerate(repdata):
            if reptup[0][1]==own_name:
                repdata=repdata[:i+6]
                break
        for reptup in repdata: # remove id,unencoded name tuples and the star indices            
            reptup.pop(5)
            reptup.pop(4)
            reptup.pop(0)
        # include rank
        for i,reptup in enumerate(repdata):
            reptup.insert(0, i+1)
        report=tabulate.tabulate(repdata, floatfmt='.1f', tablefmt='text',
         headers=['Rank', 'Name', 'First * (min.)', 'Second * (min.)', 'Score'])
        print(f'Ranking for day {daynum} of {year}:')
        print(report)
        print()
    return total_points

def show_totals(own_name, total_points, year):
    repdata=[]
    for id_name, points in total_points.items():
        id=id_name[0]
        name=id_name[1]
        name_enc=encode_name(name, id)
        repdata.append([name, name_enc, points])
    repdata.sort(key=lambda reptup: -reptup[-1])
    # truncate somewhere below own position to avoid making the list too long
    for i,reptup in enumerate(repdata):
        if reptup[0]==own_name:
            repdata=repdata[:i+20]
            break
    for reptup in repdata: # remove unencoded names
            reptup.pop(0)
    # include rank
    for i,reptup in enumerate(repdata):
        reptup.insert(0, i+1)            
    report=tabulate.tabulate(repdata, floatfmt='.1f', tablefmt='text',
     headers=['Rank', 'Name', 'Total score'])
    print(f'Total ranking for {year}:')
    print(report)

def show_own_times(own_name, data, year):
    '''for each day where you competed show your own time in minutes'''
    # search own_id
    own_id=None
    for key, tsdata in data.items():
        if tsdata['name']!=own_name:
            continue
        if own_id is None:
            own_id=key[1]
        else:
            assert own_id==key[1] # could be multiple people with same name, if so would have to
                                  # rewrite all code to use own_id instead of own_name, and
                                  # specify own_id manually
    # gather times per day
    repdata=[]
    for daynum in range(1, 26):
        tsdata=data.get( (daynum, own_id) )
        if tsdata is None:
            continue
        star1min=(tsdata['star1']-tsdata['start'])/60.0 if 'star1' in tsdata else None
        star2min=(tsdata['star2']-tsdata['start'])/60.0 if 'star2' in tsdata else None
        repdata.append([daynum, star1min, star2min])
    print(f'Times for {year}:')
    report=tabulate.tabulate(repdata, floatfmt='.1f', tablefmt='text',
        headers=['Day', 'First * (min.)', 'Second * (min.)'])
    print(report)
    print()
    repdata.sort(key=lambda reptup: reptup[0] if reptup[2] is None else -reptup[2])
    print(f'Hardest for {year}:')
    report=tabulate.tabulate(repdata, floatfmt='.1f', tablefmt='text',
        headers=['Day', 'First * (min.)', 'Second * (min.)'])
    print(report)

def main(own_name, ownonly, inputfiles):
    notebooks=glob.glob('*.ipynb')
    total_yds=[]
    for n in notebooks:
        list_yds=notebook2yds(n)
        total_yds.extend(list_yds)
    data=None
    year=None
    num_participants=0
    for inputfile in inputfiles:
        data, year, num_participants=get_timestamps(own_name, total_yds, inputfile, data, year, len(inputfiles)>1)
    assert data is not None
    assert year is not None
    check_data(data, num_participants)
    if ownonly:
        show_own_times(own_name, data, year)
    else:
        total_points=show_report(own_name, data, year, num_participants)
        show_totals(own_name, total_points, year)

if __name__ == '__main__':
    if len(sys.argv)<3:
        raise ValueError("usage: python privaterank.py [-ownonly] 'Own Name' leaderboard.json...")
    own_name=None
    ownonly=False
    inputfiles=[]
    for s in sys.argv[1:]:
        if s.startswith('-'):
            if s=='-ownonly':
                ownonly=True
            else:
                raise ValueError("only supported option is -ownonly")
        elif own_name is None:
            own_name=s
        else:
            inputfiles.append(s)
    main(own_name, ownonly, inputfiles)
