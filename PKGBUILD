# Maintainer: Oscar Krause <oscar.krause@collinwebdesigns.de>
pkgname=fastapi-dls
pkgver=1.0.0
pkgrel=3
pkgdesc="Minimal Delegated License Service (DLS)."
arch=('any')
url="https://git.collinwebdesigns.de/oscar.krause/fastapi-dls"
#license=('MIT')
depends=('python3' 'python-fastapi' 'uvicorn' 'python-dotenv' 'python-dateutil' 'python-jose' 'python-sqlalchemy' 'python-pycryptodome' 'python-markdown' 'openssl')
#source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
#sha256sums=('...')

check() {
    cd "$pkgname-$pkgver"
    python3 "$pkgname.py" --version
}

package() {
    cd "$pkgname-$pkgver"
    install -m 755 -TD "$pkgname.py" "$pkgdir/usr/bin/$pkgname"
    install -m 644 -TD "README.md" "$pkgdir/usr/share/doc/$pkgname/README.md"
    install -m 644 -TD "LICENSE" "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
