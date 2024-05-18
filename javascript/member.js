a.b = 5;
a[0] = 6;
a.c();
function a()
{return num < 0 ? this[ num + this.length ] : this[ num ]; }