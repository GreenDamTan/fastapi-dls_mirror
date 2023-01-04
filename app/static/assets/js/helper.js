async function fetchConfig(element) {
    let xhr = new XMLHttpRequest();
    xhr.open("GET", '/-/config', true);
    xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            element.innerHTML = JSON.stringify(JSON.parse(xhr.response),null,2);
        }
    };
    xhr.send();
}

async function fetchOriginsWithLeases(element) {
    let xhr = new XMLHttpRequest();
    xhr.open("GET", '/-/origins?leases=true', true);
    xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            const x = JSON.parse(xhr.response)
            console.debug(x)

            element.innerHTML = ''
            let table = document.createElement('table')
            table.classList.add('table', 'mt-4');
            let thead = document.createElement('thead');
            thead.innerHTML = `
                    <tr>
                        <th scope="col">origin</th>
                        <th scope="col">hostname</th>
                        <th scope="col">OS</th>
                        <th scope="col">driver version</th>
                        <th scope="col">leases</th>
                    </tr>`
            table.appendChild(thead)
            let tbody = document.createElement('thead');
            x.sort((a, b) => a.hostname.localeCompare(b.hostname)).forEach((o) => {
                let row = document.createElement('tr');
                row.innerHTML = `
                        <td><code>${o.origin_ref}</code></td>
                        <td>${o.hostname}</td>
                        <td>${o.os_platform} (${o.os_version})</td>
                        <td>${o.guest_driver_version}</td>
                        <td>${o.leases.map(x => `<code title="expires: ${x.lease_expires}">${x.lease_ref}</code>`).join(', ')}</td>`
                tbody.appendChild(row);
            })
            table.appendChild(tbody)
            element.appendChild(table)
        }
    };
    xhr.send();
}

async function fetchLeases(element) {
    // datetime config
    const dtc = {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZoneName: "short"
    }

    let xhr = new XMLHttpRequest();
    xhr.open("GET", '/-/leases?origin=true', true);
    xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            const x = JSON.parse(xhr.response)
            console.debug(x)

            element.innerHTML = ''
            let table = document.createElement('table')
            table.classList.add('table', 'mt-4');
            let thead = document.createElement('thead');
            thead.innerHTML = `
                    <tr>
                        <th scope="col">lease</th>
                        <th scope="col">created</th>
                        <th scope="col">updated</th>
                        <th scope="col">expires</th>
                        <th scope="col">origin</th>
                    </tr>`
            table.appendChild(thead)
            let tbody = document.createElement('thead');
            x.sort((a, b) => new Date(a.lease_expires) - new Date(b.lease_expires)).forEach((o) => {
                let row = document.createElement('tr');
                row.innerHTML = `
                        <td><code>${o.lease_ref}</code></td>
                        <td>${new Date(o.lease_created).toLocaleDateString('system', dtc)}</td>
                        <td>${new Date(o.lease_updated).toLocaleDateString('system', dtc)}</td>
                        <td>${new Date(o.lease_expires).toLocaleDateString('system', dtc)}</td>
                        <td><code title="hostname: ${x.origin.hostname}">${o.origin_ref}</code></td>`
                tbody.appendChild(row);
            })
            table.appendChild(tbody)
            element.appendChild(table)
        }
    };
    xhr.send();
}

async function deleteOrigins() {
    let xhr = new XMLHttpRequest();
    xhr.open("DELETE", '/-/origins', true);
    xhr.send();
}

async function deleteOrigin(origin_ref) {
    if (origin_ref === undefined)
        origin_ref = window.prompt("Please enter 'origin_ref' which should be deleted");
    if (origin_ref === null || origin_ref === "")
        return
    let xhr = new XMLHttpRequest();
    xhr.open("DELETE", `/-/origins/${origin_ref}`, true);
    xhr.send();
}

async function deleteLease(lease_ref) {
    if (lease_ref === undefined)
        lease_ref = window.prompt("Please enter 'lease_ref' which should be deleted");
    if (lease_ref === null || lease_ref === "")
        return
    let xhr = new XMLHttpRequest();
    xhr.open("DELETE", `/-/lease/${{lease_ref}}`, true);
    xhr.send();
}
