# Maintainer: samicrusader <hi@samicrusader.me>
# Maintainer: Oscar Krause <oscar.krause@collinwebdesigns.de>

pkgname=fastapi-dls
pkgver=1.0
pkgrel=1
pkgdesc='NVIDIA DLS server implementation with FastAPI'
arch=('any')
url='https://git.collinwebdesigns.de/oscar.krause/fastapi-dls'
license=('MIT')
depends=('python' 'python-jose' 'python-starlette' 'python-httpx' 'python-fastapi' 'python-dotenv' 'python-dateutil' 'python-sqlalchemy' 'python-pycryptodome' 'uvicorn' 'python-markdown' 'openssl')
provider=("$pkgname")
install="$pkgname.install"
source=('git+https://git.collinwebdesigns.de/oscar.krause/fastapi-dls.git#commit=3d5203dae054020e6f56e5f457fac1fbacc6f05d' # https://gitea.publichub.eu/oscar.krause/fastapi-dls.git
        "$pkgname.default"
        "$pkgname.service")
sha256sums=('SKIP'
            'd8b2216b67a2f8f35ad6f07c825839794f7c34456a72caadd9fc110810348d90'
            '10cb98d64f8bf37b11a60510793c187cc664e63c895d1205781c21fa2e703f32')

check() {
    cd "$srcdir/$pkgname/test"
    mkdir "$srcdir/$pkgname/app/cert"
    openssl genrsa -out "$srcdir/$pkgname/app/cert/instance.private.pem" 2048
    openssl rsa -in "$srcdir/$pkgname/app/cert/instance.private.pem" -outform PEM -pubout -out "$srcdir/$pkgname/app/cert/instance.public.pem"
    python "$srcdir/$pkgname/test/main.py"
    rm -rf "$srcdir/$pkgname/app/cert"
}

package() {
    install -d "$pkgdir/usr/share/doc/$pkgname"
    install -d "$pkgdir/var/lib/$pkgname/cert"
    cp -r "$srcdir/$pkgname/doc"/* "$pkgdir/usr/share/doc/$pkgname/"
    install -Dm644 "$srcdir/$pkgname/README.md" "$pkgdir/usr/share/doc/$pkgname/README.md"

    sed -i "s/README.md/\/usr\/share\/doc\/$pkgname\/README.md/g" "$srcdir/$pkgname/app/main.py"
    sed -i "s/join(dirname(__file__), 'cert\//join('\/var\/lib\/$pkgname', 'cert\//g" "$srcdir/$pkgname/app/main.py"
    install -Dm755 "$srcdir/$pkgname/app/main.py" "$pkgdir/opt/$pkgname/main.py"
    install -Dm755 "$srcdir/$pkgname/app/orm.py" "$pkgdir/opt/$pkgname/orm.py"
    install -Dm644 "$srcdir/$pkgname.default" "$pkgdir/etc/default/$pkgname"
    install -Dm644 "$srcdir/$pkgname.service" "$pkgdir/usr/lib/systemd/system/$pkgname.service"
}
