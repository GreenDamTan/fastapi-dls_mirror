# Maintainer: Oscar Krause <oscar.krause@collinwebdesigns.de>
pkgname=fastapi-dls
pkgver=1.0.0
pkgrel=1
pkgdesc="Minimal Delegated License Service (DLS)."
arch=('any')  # x86_64?
url="https://git.collinwebdesigns.de/oscar.krause/fastapi-dls"
#license=('MIT')
depends=('python3' 'python-fastapi' 'uvicorn' 'python-dotenv' 'python-dateutil' 'python-jose' 'python-sqlalchemy' 'python-pycryptodome' 'python-markdown' 'openssl')
source=('README.md' 'version.env' 'app/main.py' 'app/orm.py' 'app/util.py')
sha512sums=("SKIP")

package() {
  mkdir -p "${pkgdir}/usr/share"

  cp "${srcdir}/README.md" "${pkgdir}/usr/share/README.md"
  cp "${srcdir}/version.env" "${pkgdir}/usr/share/version.env"
  cp -r "${srcdir}/app" "${pkgdir}/usr/share"
}
