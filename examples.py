prog0 = '''
var x , y ;
begin
  x := 0 ;
  while x < 10 do
    begin
      if x < 5 then x := 5 ;
      x := x + 1
    end ;
  y := x ;
  ! y
end .
'''

prog0a = '''
var x , y ;
procedure hello ;
  x := y ;
begin
  x := 0 ;
  while x < 10 do
    begin
      if x < 5 then x := 5 ;
      x := x + 1
    end ;
  y := x ;
  ! y
end .
'''

prog1 = '''
var x , squ ;
procedure square ;
begin
  squ := x * x
end ;
begin
  x := 1 ;
  while x <= 10 do
  begin
    call square ;
    ! squ ;
    x := x + 1
  end
end .
'''

prog2 = '''
const max = 100 ;
var arg , ret ;

procedure isprime ;
var i ;
begin
  ret := 1 ;
  i := 2 ;
  while i < arg do
  begin
    if arg / i * i == arg then
    begin
      ret := 0 ;
      i := arg
    end ;
    i := i + 1
  end
end ;

procedure primes ;
begin
  arg := 2 ;
  while arg < max do
  begin
    call isprime ;
    if ret == 1 then ! arg ;
    arg := arg + 1
  end
end ;

call primes
.
'''

prog3 = '''
var x , y , z , q , r , n , f ;

procedure multiply ;
var a , b ;
begin
  a := x ;
  b := y ;
  z := 0 ;
  while b > 0 do
  begin
    if odd b then z := z + a ;
    a := 2 * a ;
    b := b / 2
  end
end ;

procedure divide ;
var w ;
begin
  r := x ;
  q := 0 ;
  w := y ;
  while w <= r do w := 2 * w ;
  while w > y do
  begin
    q := 2 * q ;
    w := w / 2 ;
    if w <= r then
    begin
      r := r - w ;
      q := q + 1
    end
  end
end ;

procedure gcd ;
var f , g ;
begin
  f := x ;
  g := y ;
  while f != g do
  begin
    if f < g then g := g - f ;
    if g < f then f := f - g
  end ;
  z := f
end ;

procedure fact ;
begin
  if n > 1 then
  begin
    f := n * f ;
    n := n - 1 ;
    call fact
  end
end ;

begin
  ? x ; ? y ; call multiply ; ! z ;
  ? x ; ? y ; call divide ; ! q ; ! r ;
  ? x ; ? y ; call gcd ; ! z ;
  ? n ; f := 1 ; call fact ; ! f
end .
'''

prog4 = '''
const x = 100 ;
var y , z ;
procedure foo ;
	const w = 200 ;
	var a , b , c ;
	procedure bar ;
		const q = 300 ;
		var m , n ;
		begin
			m := a ;
			n := m + b ;
			b := n * c
		end ;
	begin 
		a := w + z ;
		b := y ;
		c := x ;
		call bar ;
		y := a ;
		z := b
	end ;
begin
	y := 0 ;
	z := 1 ;
	call foo
end .
'''

prog5 = '''
procedure foo ;
  var a ;
begin
  a := 1
end ;
while 1 == 1 do
  while 2 == 2 do
  begin
  if 4 == 4 then
    while 3 == 3 do
      call foo ;
  while 4 == 4 do
    call foo
  end .
'''
