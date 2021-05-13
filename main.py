import requests
from pprint import pprint
import json
import subprocess
from csv import reader
import csv


def convert_to_csv(list):
    with open('list.csv', 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['Email', 'Manager', 'Department'])
        for row in list:
            csv_out.writerow(row)


def get_secret(file):
    with open(file, 'r') as file:
        return file.read().replace('\n', '')


def dm_snitch():
    requests.post(get_secret('snitch.txt'))


def create_row_map(row):
    return {
        'primary_email': row[0],
        'relation_value': row[8],
        'department': row[5],
    }


def format_email_content(content):
    content.insert(0, ['User', 'Manager', 'Department'])
    new_content = ''
    length_list = [len(element) for row in content for element in row]
    column_width = max(length_list)
    for row in content:
        row = "".join(element.ljust(column_width + 2) for element in row)
        new_content = new_content + "\n" + row

    return new_content


class Namely:

    def __init__(self, token, gam_binary_path):
        self.session = requests.Session()
        self.base_url = 'https://company.namely.com/api/v1'
        self.report_id = ''  # Active
        # Employees Report

        # GAM is expected to read from for setting a value
        self.auth_token = token
        self.gam_path = gam_binary_path

    def send_api(self, method, endpoint, **kwargs):
        url = '{}{}'.format(self.base_url, endpoint)
        request = requests.Request(method,
                                   url,
                                   headers=self.get_headers(),
                                   **kwargs)
        prepped = request.prepare()
        response = self.session.send(prepped)
        response.raise_for_status()
        return response

    def get_headers(self):
        return {
            'Accept': 'application/json',
            'Authorization': 'Bearer {}'.format(self.auth_token)
        }

    def get_active_employee_report(self):
        report_path = f"/reports/{self.report_id}"
        try:
            res = self.send_api('GET', report_path)
            return res.json().get('reports')[0]
        except requests.exceptions.HTTPError as ex:
            print(f"Request to get Namely report failed, error={ex}")
            exit(1)

    def get_employees_from_namely(self):
        report = self.get_active_employee_report()
        parsed = [value for value in report['content'] if value[2]]
        return parsed

    def get_gam_list(self):
        subprocess.run(
            "{} print users custom all relations organizations > "
            "report.csv".format(self.gam_path),
            capture_output=True, shell=True)
        with open('report.csv') as f:
            next(csv.reader(f), None)
            data = [create_row_map(row) for row in csv.reader(f)]
            res = [*[list(idx.values()) for idx in data]]
            return res

    def update_google(self):
        return subprocess.run(
            "{} csv list.csv gam update user ~Email relation "
            "manager ~Manager organization department ~Department".format
            (self.gam_path), capture_output=True,
            check=True, shell=True)

    def email(self, content, new_content):
        return subprocess.run('{} '
                              'sendemail it@company.io from '
                              'it-noreply@company.io subject '
                              '"Google/Namely Sync Actions" message "Users '
                              'Google Profiles Updated to:'
                              '\n\nBefore:{}\n\n\nAfter:{}"'.
                              format(self.gam_path, content, new_content),
                              capture_output=True,
                              check=True, shell=True)


def main():
    drive = Namely(
        get_secret('token.txt'), '/opt/gam/src/gam.py')

    # Pairs for both instances are defined as [user_email, manager_email]
    email_pairs_namely = drive.get_employees_from_namely()
    email_pairs_google = drive.get_gam_list()
    # Here we grab the delta between the two lists of pairs. We exclude two..
    delta = [pair for pair in email_pairs_namely if
             pair not in email_pairs_google if
             pair[0] not in OMITTED_EMAILS]

    delta_of_delta = [j for j in email_pairs_google for i in delta if
                      j[0]
                      in i[0]]

    if not delta:
        dm_snitch()
        exit()

    convert_to_csv(delta)
    drive.update_google()
    drive.email(format_email_content(delta_of_delta),
                format_email_content(delta))
    dm_snitch()


if __name__ == "__main__":
    main()
