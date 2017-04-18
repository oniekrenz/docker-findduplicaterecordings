# coding=UTF-8

import argparse
import difflib
import json
import os
import re
import time

from pyexcel_ods import get_data

argparser = argparse.ArgumentParser()
argparser.add_argument('jobfile', help='JSON file with removal jobs (UTF-8)')
argparser.add_argument('-t', '--test', help='test only, do not remove files', action="store_true")
args = argparser.parse_args()

condition_pattern = re.compile('^(.*?)(\$(\d))(.*)')
interval_in_sec = 60


def subst_condition(condition, row):
    while True:
        match = condition_pattern.match(condition)
        if match:
            row_num = int(match.group(3))
            row_val = row[row_num] if len(row) > row_num else ''
            condition = match.group(1) + row_val + match.group(4)
        else:
            break
    return condition


def get_job_definitions(filename):
    jobs = []
    with open(filename, 'r') as job_definition_file:
        job_definition = json.load(job_definition_file, 'UTF-8')
        root_dir = os.path.abspath(os.path.dirname(filename))
        for entry in job_definition:
            job_id = entry['id']
            job_filename = entry['file']
            job_filename = job_filename if os.path.isabs(job_filename) else os.path.join(root_dir, job_filename)
            job_filename = os.path.abspath(job_filename)
            title = entry['title']
            recordings_dir = entry['recordings_dir']
            recordings_dir = recordings_dir if os.path.isabs(recordings_dir) else os.path.join(root_dir, recordings_dir)
            recordings_dir = os.path.abspath(recordings_dir)
            subtitle_column = int(entry['subtitle_column'])
            data = get_data(job_filename)
            valid_row_condition = entry['valid_row_condition'] if 'valid_row_condition' in entry else 'True'
            known_subtitle_condition = entry['known_subtitle_condition'] \
                if 'known_subtitle_condition' in entry else 'True'
            sheet = data[entry['sheet']]
            subtitles = []
            for row_index, row in enumerate(sheet):
                subst_row_condition = subst_condition(valid_row_condition, row)
                valid_row = eval(subst_row_condition, {'__builtins__': {}})
                if valid_row and (len(row) >= subtitle_column) and row[subtitle_column]:
                    subst_subtitle_condition = subst_condition(known_subtitle_condition, row)
                    is_known_subtitle = eval(subst_subtitle_condition, {'__builtins__': {}})
                    if is_known_subtitle:
                        subtitles.append(row[subtitle_column])
            print 'Found ' + str(len(subtitles)) + ' subtitles for "' + job_id + '"'
            jobs.append({
                'id': job_id,
                'dir': recordings_dir,
                'title': title,
                'subtitles': subtitles
            })
    return jobs


def normalize(s):
    s = s.lower()
    s = s.replace(u'ß', 'ss').replace(u'ä', 'a').replace(u'ö', 'o').replace(u'ü', 'u')
    s = re.sub(r'[:]', '', s)
    s = re.sub(r'[^a-z0-9]', ' ', s)
    s = re.sub(r' +', ' ', s)
    return s


def keep_file(filename, title, subtitles):
    filename_n = normalize(filename)
    title_n = normalize(title)
    pos = filename_n.find(title_n)
    if pos < 0:
        return True  # file name does not contain title, keep unknown file
    pos = pos + len(title_n) + 1
    x = filename_n[pos:]
    # print 'checking ' + filename + ' title "' + x + '"'
    for subtitle in subtitles:
        subtitle_n = normalize(subtitle)
        similarity = difflib.SequenceMatcher(a=x[:len(subtitle_n)], b=subtitle_n).ratio()
        # print '  similarity ' + str(similarity) + ' for ' + subtitle_n
        if similarity > 0.95:
            # print '  ### found match'
            return False  # in list of known subtitles, delete file
    return True  # not in list of known subtitles, keep file


def file_created_before(file_stat, timestamp):
    return file_stat.st_ctime < timestamp


def get_or_create_last_scan(job_id, filename):
    last_scans_for_id = last_scans[job_id] if job_id in last_scans else []
    matches = [f for f in last_scans_for_id if ('file' in f) and (f['file'] == filename)] or []
    return matches[0] if len(matches) > 0 else {'file': filename}


def save_last_scans(job_id, last_scans_for_id):
    last_scans[job_id] = last_scans_for_id


def has_size_changed(last_scan, file_stat):
    last_size = last_scan['size'] if 'size' in last_scan else 0
    stable_iterations = last_scan['stable_iterations'] if 'stable_iterations' in last_scan else 0
    last_scan['size'] = file_stat.st_size
    if last_size != file_stat.st_size:
        last_scan['stable_iterations'] = 0
        return True
    else:
        stable_iterations += 1
        last_scan['stable_iterations'] = stable_iterations
        return stable_iterations < 3


def move_file(full_filename, target_dir):
    if args.test:
        print 'would move "' + full_filename + '" to "' + target_dir + '"'
    else:
        path, filename = os.path.split(full_filename)
        delete_dir = os.path.join(path, target_dir)
        if not os.path.isdir(delete_dir):
            os.mkdir(delete_dir)
        os.rename(full_filename, os.path.join(delete_dir, filename))


def delete_file(full_filename):
    if args.test:
        print 'would delete "' + full_filename + '"'
    else:
        os.remove(full_filename)


def exec_jobs(jobs):
    ten_minutes_ago = time.time() - (10 * 60)
    for job in jobs:
        job_id = job['id']
        path = job['dir']
        title = job['title'] if 'title' in job else '#'
        subtitles = job['subtitles'] if 'subtitles' in job else []
        action = job['action'] if 'action' in job else 'move'
        new_last_scans = []
        for filename in os.listdir(path):
            if re.match('.*\.ts$', filename):
                full_filename = os.path.join(path, filename)
                file_stat = os.stat(full_filename)
                if file_created_before(file_stat, ten_minutes_ago) and not keep_file(filename, title, subtitles):
                    last_scan = get_or_create_last_scan(job_id, filename)
                    size_changed = has_size_changed(last_scan, file_stat)
                    if not size_changed:
                        if action == 'move':
                            move_to = job['move_to'] if 'move_to' in job else 'duplicate'
                            move_file(full_filename, move_to)
                        if action == 'delete':
                            delete_file(full_filename)
                    new_last_scans.append(last_scan)
        save_last_scans(job_id, new_last_scans)


def main():
    try:
        while True:
            jobs = get_job_definitions(args.jobfile)
            exec_jobs(jobs)

            for job_id in last_scans:
                for ls in last_scans[job_id]:
                    print ls

            time.sleep(interval_in_sec)
    except KeyboardInterrupt:
        pass


last_scans = {}
main()
