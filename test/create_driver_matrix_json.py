import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

URL = 'https://docs.nvidia.com/grid/'

BRANCH_STATUS_KEY, SOFTWARE_BRANCH_KEY, = 'vGPU Branch Status', 'vGPU Software Branch'
VGPU_KEY, GRID_KEY, DRIVER_BRANCH_KEY = 'vGPU Software', 'vGPU Software', 'Driver Branch'
LINUX_VGPU_MANAGER_KEY, LINUX_DRIVER_KEY = 'Linux vGPU Manager', 'Linux Driver'
WINDOWS_VGPU_MANAGER_KEY, WINDOWS_DRIVER_KEY = 'Windows vGPU Manager', 'Windows Driver'
ALT_VGPU_MANAGER_KEY = 'vGPU Manager'
RELEASE_DATE_KEY, LATEST_KEY, EOL_KEY = 'Release Date', 'Latest Release in Branch', 'EOL Date'
JSON_RELEASES_KEY = '$releases'


def __driver_versions(html: 'BeautifulSoup'):
    def __strip(_: str) -> str:
        # removes content after linebreak (e.g. "Hello\n World" to "Hello")
        _ = _.strip()
        tmp = _.split('\n')
        if len(tmp) > 0:
            return tmp[0]
        return _

    # find wrapper for "DriverVersions" and find tables
    data = html.find('div', {'id': 'DriverVersions'})
    tables = data.findAll('table')
    for table in tables:
        # parse software-branch (e.g. "vGPU software 17 Releases" and remove " Releases" for "matrix_key")
        software_branch = table.parent.find_previous_sibling('button', {'class': 'accordion'}).text.strip()
        software_branch = software_branch.replace(' Releases', '')
        matrix_key = software_branch.lower()

        # driver version info from table-heads (ths) and table-rows (trs)
        ths, trs = table.find_all('th'), table.find_all('tr')
        headers, releases = [header.text.strip() for header in ths], []
        for trs in trs:
            tds = trs.find_all('td')
            if len(tds) == 0:  # skip empty
                continue
            # create dict with table-heads as key and cell content as value
            x = {headers[i]: __strip(cell.text) for i, cell in enumerate(tds)}
            releases.append(x)

        # add to matrix
        MATRIX.update({matrix_key: {JSON_RELEASES_KEY: releases}})


def __release_branches(html: 'BeautifulSoup'):
    # find wrapper for "AllReleaseBranches" and find table
    data = html.find('div', {'id': 'AllReleaseBranches'})
    table = data.find('table')

    # branch releases info from table-heads (ths) and table-rows (trs)
    ths, trs = table.find_all('th'), table.find_all('tr')
    headers = [header.text.strip() for header in ths]
    for trs in trs:
        tds = trs.find_all('td')
        if len(tds) == 0:  # skip empty
            continue
        # create dict with table-heads as key and cell content as value
        x = {headers[i]: cell.text.strip() for i, cell in enumerate(tds)}

        # get matrix_key
        software_branch = x.get(SOFTWARE_BRANCH_KEY)
        matrix_key = software_branch.lower()

        # add to matrix
        MATRIX.update({matrix_key: MATRIX.get(matrix_key) | x})


def __debug():
    # print table head
    s = f'{SOFTWARE_BRANCH_KEY:^21} | {BRANCH_STATUS_KEY:^21} | {VGPU_KEY:^13} | {LINUX_VGPU_MANAGER_KEY:^21} | {LINUX_DRIVER_KEY:^21} | {WINDOWS_VGPU_MANAGER_KEY:^21} | {WINDOWS_DRIVER_KEY:^21} | {RELEASE_DATE_KEY:>21} | {EOL_KEY:>21}'
    print(s)

    # iterate over dict & format some variables to not overload table
    for idx, (key, branch) in enumerate(MATRIX.items()):
        branch_status = branch.get(BRANCH_STATUS_KEY)
        branch_status = branch_status.replace('Branch ', '')
        branch_status = branch_status.replace('Long-Term Support', 'LTS')
        branch_status = branch_status.replace('Production', 'Prod.')

        software_branch = branch.get(SOFTWARE_BRANCH_KEY).replace('NVIDIA ', '')
        for release in branch.get(JSON_RELEASES_KEY):
            version = release.get(VGPU_KEY, release.get(GRID_KEY, ''))
            linux_manager = release.get(LINUX_VGPU_MANAGER_KEY, release.get(ALT_VGPU_MANAGER_KEY, ''))
            linux_driver = release.get(LINUX_DRIVER_KEY)
            windows_manager = release.get(WINDOWS_VGPU_MANAGER_KEY, release.get(ALT_VGPU_MANAGER_KEY, ''))
            windows_driver = release.get(WINDOWS_DRIVER_KEY)
            release_date = release.get(RELEASE_DATE_KEY)
            is_latest = release.get(VGPU_KEY) == branch.get(LATEST_KEY)

            version = f'{version} *' if is_latest else version
            eol = branch.get(EOL_KEY) if is_latest else ''
            s = f'{software_branch:^21} | {branch_status:^21} | {version:<13} | {linux_manager:<21} | {linux_driver:<21} | {windows_manager:<21} | {windows_driver:<21} | {release_date:>21} | {eol:>21}'
            print(s)


def __dump(filename: str):
    import json

    file = open(filename, 'w')
    json.dump(MATRIX, file)
    file.close()


if __name__ == '__main__':
    MATRIX = {}

    try:
        import httpx
        from bs4 import BeautifulSoup
    except Exception as e:
        logger.error(f'Failed to import module: {e}')
        logger.info('Run "pip install beautifulsoup4 httpx"')
        exit(1)

    r = httpx.get(URL)
    if r.status_code != 200:
        logger.error(f'Error loading "{URL}" with status code {r.status_code}.')
        exit(2)

    # parse html
    soup = BeautifulSoup(r.text, features='html.parser')

    # build matrix
    __driver_versions(soup)
    __release_branches(soup)

    # debug output
    __debug()

    # dump data to file
    __dump('../app/static/driver_matrix.json')
