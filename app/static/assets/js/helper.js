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
            x.forEach((o) => {
                let row = document.createElement('tr');
                row.innerHTML = `
                        <td><code>${o.origin_ref}</code></td>
                        <td>${o.hostname}</td>
                        <td>${o.os_platform}</td>
                        <td>${o.os_version}</td>
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
            x.forEach((o) => {
                let row = document.createElement('tr');
                row.innerHTML = `
                        <td><code>${o.lease_ref}</code></td>
                        <td>${o.lease_created}</td>
                        <td>${o.lease_updated}</td>
                        <td>${o.lease_expires}</td>
                        <td><code>${o.origin_ref}</code></td>`
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
    await fetchOriginsWithLeases()
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
