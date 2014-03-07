if exists("b:current_syntax")
    finish
endif

let b:current_syntax = "vialcash"

syntax keyword cashKeyword currency initial rate split rev

syntax match cashNumber "\<\%([1-9]\d*\|0\)[Ll]\=\>"
syntax match cashNumber "\<\d\+[jJ]\>"
syntax match cashNumber "\<\d\+[eE][+-]\=\d\+[jJ]\=\>"
syntax match cashNumber "\<\d\+\.\%([eE][+-]\=\d\+\)\=[jJ]\=\%(\W\|$\)\@="
syntax match cashNumber "\%(^\|\W\)\@<=\d*\.\d\+\%([eE][+-]\=\d\+\)\=[jJ]\=\>"

syntax match cashDate "\v[0-9]{4}-[0-9]{2}-[0-9]{2}"
syntax match cashComment "\v#.*$"
syntax match cashPositive "\va:[-0-9a-zA-Z:]+"
syntax match cashPositive "\vi:[-0-9a-zA-Z:]+"
syntax match cashNegative "\ve:[-0-9a-zA-Z:]+"
syntax match cashNegative "\vl:[-0-9a-zA-Z:]+"

hi link cashKeyword Boolean
hi link cashDate Boolean
hi link cashComment Comment
hi link cashNumber Number
hi link cashPositive Function
hi link cashNegative Statement
