/*!
 * jQuery JavaScript Library v1.8.3
 * http://jquery.com/
 *
 * Includes Sizzle.js
 * http://sizzlejs.com/
 *
 * Copyright 2012 jQuery Foundation and other contributors
 * Released under the MIT license
 * http://jquery.org/license
 *
 * Date: Tue Nov 13 2012 08:20:33 GMT-0500 (Eastern Standard Time)
 */
(function( window, undefined ) {
var
	// A central reference to the root jQuery(document)
	rootjQuery,

	// The deferred used on DOM ready
	readyList,

	// Use the correct document accordingly with window argument (sandbox)
	document = window.document,
	location = window.location,
	navigator = window.navigator,

	// Map over jQuery in case of overwrite
	_jQuery = window.jQuery,

	// Map over the $ in case of overwrite
	_$ = window.$,

	// Save a reference to some core methods
	core_push = Array.prototype.push,
	core_slice = Array.prototype.slice,
	core_indexOf = Array.prototype.indexOf,
	core_toString = Object.prototype.toString,
	core_hasOwn = Object.prototype.hasOwnProperty,
	core_trim = String.prototype.trim,

	// Define a local copy of jQuery
	jQuery = function( selector, context ) {
		// The jQuery object is actually just the init constructor 'enhanced'
		return new jQuery.fn.init( selector, context, rootjQuery );
	},

	// Used for matching numbers
	core_pnum = /[\-+]?(?:\d*\.|)\d+(?:[eE][\-+]?\d+|)/.source,

	// Used for detecting and trimming whitespace
	core_rnotwhite = /\S/,
	core_rspace = /\s+/,

	// Make sure we trim BOM and NBSP (here's looking at you, Safari 5.0 and IE)
	rtrim = /^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g,

	// A simple way to check for HTML strings
	// Prioritize #id over <tag> to avoid XSS via location.hash (#9521)
	rquickExpr = /^(?:[^#<]*(<[\w\W]+>)[^>]*$|#([\w\-]*)$)/,

	// Match a standalone tag
	rsingleTag = /^<(\w+)\s*\/?>(?:<\/\1>|)$/,

	// JSON RegExp
	rvalidchars = /^[\],:{}\s]*$/,
	rvalidbraces = /(?:^|:|,)(?:\s*\[)+/g,
	rvalidescape = /\\(?:["\\\/bfnrt]|u[\da-fA-F]{4})/g,
	rvalidtokens = /"[^"\\\r\n]*"|true|false|null|-?(?:\d\d*\.|)\d+(?:[eE][\-+]?\d+|)/g,

	// Matches dashed string for camelizing
	rmsPrefix = /^-ms-/,
	rdashAlpha = /-([\da-z])/gi,

	// Used by jQuery.camelCase as callback to replace()
	fcamelCase = function( all, letter ) {
		return ( letter + "" ).toUpperCase();
	},

	// The ready event handler and self cleanup method
	DOMContentLoaded = function() {
		if ( document.addEventListener ) {
			document.removeEventListener( "DOMContentLoaded", DOMContentLoaded, false );
			jQuery.ready();
		} else if ( document.readyState === "complete" ) {
			// we're here because readyState === "complete" in oldIE
			// which is good enough for us to call the dom ready!
			document.detachEvent( "onreadystatechange", DOMContentLoaded );
			jQuery.ready();
		}
	},

	// [[Class]] -> type pairs
	class2type = {};

jQuery.fn = jQuery.prototype = {
	constructor: jQuery,
	init: function( selector, context, rootjQuery ) {
		var match, elem, ret, doc;

		// Handle $(""), $(null), $(undefined), $(false)
		if ( !selector ) {
			return this;
		}

		// Handle $(DOMElement)
		if ( selector.nodeType ) {
			this.context = this[0] = selector;
			this.length = 1;
			return this;
		}

		// Handle HTML strings
		if ( typeof selector === "string" ) {
			if ( selector.charAt(0) === "<" && selector.charAt( selector.length - 1 ) === ">" && selector.length >= 3 ) {
				// Assume that strings that start and end with <> are HTML and skip the regex check
				match = [ null, selector, null ];

			} else {
				match = rquickExpr.exec( selector );
			}

			// Match html or make sure no context is specified for #id
			if ( match && (match[1] || !context) ) {

				// HANDLE: $(html) -> $(array)
				if ( match[1] ) {
					context = context instanceof jQuery ? context[0] : context;
					doc = ( context && context.nodeType ? context.ownerDocument || context : document );

					// scripts is true for back-compat
					selector = jQuery.parseHTML( match[1], doc, true );
					if ( rsingleTag.test( match[1] ) && jQuery.isPlainObject( context ) ) {
						this.attr.call( selector, context, true );
					}

					return jQuery.merge( this, selector );

				// HANDLE: $(#id)
				} else {
					elem = document.getElementById( match[2] );

					// Check parentNode to catch when Blackberry 4.6 returns
					// nodes that are no longer in the document #6963
					if ( elem && elem.parentNode ) {
						// Handle the case where IE and Opera return items
						// by name instead of ID
						if ( elem.id !== match[2] ) {
							return rootjQuery.find( selector );
						}

						// Otherwise, we inject the element directly into the jQuery object
						this.length = 1;
						this[0] = elem;
					}

					this.context = document;
					this.selector = selector;
					return this;
				}

			// HANDLE: $(expr, $(...))
			} else if ( !context || context.jquery ) {
				return ( context || rootjQuery ).find( selector );

			// HANDLE: $(expr, context)
			// (which is just equivalent to: $(context).find(expr)
			} else {
				return this.constructor( context ).find( selector );
			}

		// HANDLE: $(function)
		// Shortcut for document ready
		} else if ( jQuery.isFunction( selector ) ) {
			return rootjQuery.ready( selector );
		}

		if ( selector.selector !== undefined ) {
			this.selector = selector.selector;
			this.context = selector.context;
		}

		return jQuery.makeArray( selector, this );
	},

	// Start with an empty selector
	selector: "",

	// The current version of jQuery being used
	jquery: "1.8.3",

	// The default length of a jQuery object is 0
	length: 0,

	// The number of elements contained in the matched element set
	size: function() {
		return this.length;
	},

	toArray: function() {
		return core_slice.call( this );
	},

	// Get the Nth element in the matched element set OR
	// Get the whole matched element set as a clean array
	get: function( num ) {
		return num == null ?

			// Return a 'clean' array
			this.toArray() :

			// Return just the object
			( num < 0 ? this[ this.length + num ] : this[ num ] );
	},

	// Take an array of elements and push it onto the stack
	// (returning the new matched element set)
	pushStack: function( elems, name, selector ) {

		// Build a new jQuery matched element set
		var ret = jQuery.merge( this.constructor(), elems );

		// Add the old object onto the stack (as a reference)
		ret.prevObject = this;

		ret.context = this.context;

		if ( name === "find" ) {
			ret.selector = this.selector + ( this.selector ? " " : "" ) + selector;
		} else if ( name ) {
			ret.selector = this.selector + "." + name + "(" + selector + ")";
		}

		// Return the newly-formed element set
		return ret;
	},

	// Execute a callback for every element in the matched set.
	// (You can seed the arguments with an array of args, but this is
	// only used internally.)
	each: function( callback, args ) {
		return jQuery.each( this, callback, args );
	},

	ready: function( fn ) {
		// Add the callback
		jQuery.ready.promise().done( fn );

		return this;
	},

	eq: function( i ) {
		i = +i;
		return i === -1 ?
			this.slice( i ) :
			this.slice( i, i + 1 );
	},

	first: function() {
		return this.eq( 0 );
	},

	last: function() {
		return this.eq( -1 );
	},

	slice: function() {
		return this.pushStack( core_slice.apply( this, arguments ),
			"slice", core_slice.call(arguments).join(",") );
	},

	map: function( callback ) {
		return this.pushStack( jQuery.map(this, function( elem, i ) {
			return callback.call( elem, i, elem );
		}));
	},

	end: function() {
		return this.prevObject || this.constructor(null);
	},

	// For internal use only.
	// Behaves like an Array's method, not like a jQuery method.
	push: core_push,
	sort: [].sort,
	splice: [].splice
};

// Give the init function the jQuery prototype for later instantiation
jQuery.fn.init.prototype = jQuery.fn;

jQuery.extend = jQuery.fn.extend = function() {
	var options, name, src, copy, copyIsArray, clone,
		target = arguments[0] || {},
		i = 1,
		length = arguments.length,
		deep = false;

	// Handle a deep copy situation
	if ( typeof target === "boolean" ) {
		deep = target;
		target = arguments[1] || {};
		// skip the boolean and the target
		i = 2;
	}

	// Handle case when target is a string or something (possible in deep copy)
	if ( typeof target !== "object" && !jQuery.isFunction(target) ) {
		target = {};
	}

	// extend jQuery itself if only one argument is passed
	if ( length === i ) {
		target = this;
		--i;
	}

	for ( ; i < length; i++ ) {
		// Only deal with non-null/undefined values
		if ( (options = arguments[ i ]) != null ) {
			// Extend the base object
			for ( name in options ) {
				src = target[ name ];
				copy = options[ name ];

				// Prevent never-ending loop
				if ( target === copy ) {
					continue;
				}

				// Recurse if we're merging plain objects or arrays
				if ( deep && copy && ( jQuery.isPlainObject(copy) || (copyIsArray = jQuery.isArray(copy)) ) ) {
					if ( copyIsArray ) {
						copyIsArray = false;
						clone = src && jQuery.isArray(src) ? src : [];

					} else {
						clone = src && jQuery.isPlainObject(src) ? src : {};
					}

					// Never move original objects, clone them
					target[ name ] = jQuery.extend( deep, clone, copy );

				// Don't bring in undefined values
				} else if ( copy !== undefined ) {
					target[ name ] = copy;
				}
			}
		}
	}

	// Return the modified object
	return target;
};

jQuery.extend({
	noConflict: function( deep ) {
		if ( window.$ === jQuery ) {
			window.$ = _$;
		}

		if ( deep && window.jQuery === jQuery ) {
			window.jQuery = _jQuery;
		}

		return jQuery;
	},

	// Is the DOM ready to be used? Set to true once it occurs.
	isReady: false,

	// A counter to track how many items to wait for before
	// the ready event fires. See #6781
	readyWait: 1,

	// Hold (or release) the ready event
	holdReady: function( hold ) {
		if ( hold ) {
			jQuery.readyWait++;
		} else {
			jQuery.ready( true );
		}
	},

	// Handle when the DOM is ready
	ready: function( wait ) {

		// Abort if there are pending holds or we're already ready
		if ( wait === true ? --jQuery.readyWait : jQuery.isReady ) {
			return;
		}

		// Make sure body exists, at least, in case IE gets a little overzealous (ticket #5443).
		if ( !document.body ) {
			return setTimeout( jQuery.ready, 1 );
		}

		// Remember that the DOM is ready
		jQuery.isReady = true;

		// If a normal DOM Ready event fired, decrement, and wait if need be
		if ( wait !== true && --jQuery.readyWait > 0 ) {
			return;
		}

		// If there are functions bound, to execute
		readyList.resolveWith( document, [ jQuery ] );

		// Trigger any bound ready events
		if ( jQuery.fn.trigger ) {
			jQuery( document ).trigger("ready").off("ready");
		}
	},

	// See test/unit/core.js for details concerning isFunction.
	// Since version 1.3, DOM methods and functions like alert
	// aren't supported. They return false on IE (#2968).
	isFunction: function( obj ) {
		return jQuery.type(obj) === "function";
	},

	isArray: Array.isArray || function( obj ) {
		return jQuery.type(obj) === "array";
	},

	isWindow: function( obj ) {
		return obj != null && obj == obj.window;
	},

	isNumeric: function( obj ) {
		return !isNaN( parseFloat(obj) ) && isFinite( obj );
	},

	type: function( obj ) {
		return obj == null ?
			String( obj ) :
			class2type[ core_toString.call(obj) ] || "object";
	},

	isPlainObject: function( obj ) {
		// Must be an Object.
		// Because of IE, we also have to check the presence of the constructor property.
		// Make sure that DOM nodes and window objects don't pass through, as well
		if ( !obj || jQuery.type(obj) !== "object" || obj.nodeType || jQuery.isWindow( obj ) ) {
			return false;
		}

		try {
			// Not own constructor property must be Object
			if ( obj.constructor &&
				!core_hasOwn.call(obj, "constructor") &&
				!core_hasOwn.call(obj.constructor.prototype, "isPrototypeOf") ) {
				return false;
			}
		} catch ( e ) {
			// IE8,9 Will throw exceptions on certain host objects #9897
			return false;
		}

		// Own properties are enumerated firstly, so to speed up,
		// if last one is own, then all properties are own.

		var key;
		for ( key in obj ) {}

		return key === undefined || core_hasOwn.call( obj, key );
	},

	isEmptyObject: function( obj ) {
		var name;
		for ( name in obj ) {
			return false;
		}
		return true;
	},

	error: function( msg ) {
		throw new Error( msg );
	},

	// data: string of html
	// context (optional): If specified, the fragment will be created in this context, defaults to document
	// scripts (optional): If true, will include scripts passed in the html string
	parseHTML: function( data, context, scripts ) {
		var parsed;
		if ( !data || typeof data !== "string" ) {
			return null;
		}
		if ( typeof context === "boolean" ) {
			scripts = context;
			context = 0;
		}
		context = context || document;

		// Single tag
		if ( (parsed = rsingleTag.exec( data )) ) {
			return [ context.createElement( parsed[1] ) ];
		}

		parsed = jQuery.buildFragment( [ data ], context, scripts ? null : [] );
		return jQuery.merge( [],
			(parsed.cacheable ? jQuery.clone( parsed.fragment ) : parsed.fragment).childNodes );
	},

	parseJSON: function( data ) {
		if ( !data || typeof data !== "string") {
			return null;
		}

		// Make sure leading/trailing whitespace is removed (IE can't handle it)
		data = jQuery.trim( data );

		// Attempt to parse using the native JSON parser first
		if ( window.JSON && window.JSON.parse ) {
			return window.JSON.parse( data );
		}

		// Make sure the incoming data is actual JSON
		// Logic borrowed from http://json.org/json2.js
		if ( rvalidchars.test( data.replace( rvalidescape, "@" )
			.replace( rvalidtokens, "]" )
			.replace( rvalidbraces, "")) ) {

			return ( new Function( "return " + data ) )();

		}
		jQuery.error( "Invalid JSON: " + data );
	},

	// Cross-browser xml parsing
	parseXML: function( data ) {
		var xml, tmp;
		if ( !data || typeof data !== "string" ) {
			return null;
		}
		try {
			if ( window.DOMParser ) { // Standard
				tmp = new DOMParser();
				xml = tmp.parseFromString( data , "text/xml" );
			} else { // IE
				xml = new ActiveXObject( "Microsoft.XMLDOM" );
				xml.async = "false";
				xml.loadXML( data );
			}
		} catch( e ) {
			xml = undefined;
		}
		if ( !xml || !xml.documentElement || xml.getElementsByTagName( "parsererror" ).length ) {
			jQuery.error( "Invalid XML: " + data );
		}
		return xml;
	},

	noop: function() {},

	// Evaluates a script in a global context
	// Workarounds based on findings by Jim Driscoll
	// http://weblogs.java.net/blog/driscoll/archive/2009/09/08/eval-javascript-global-context
	globalEval: function( data ) {
		if ( data && core_rnotwhite.test( data ) ) {
			// We use execScript on Internet Explorer
			// We use an anonymous function so that context is window
			// rather than jQuery in Firefox
			( window.execScript || function( data ) {
				window[ "eval" ].call( window, data );
			} )( data );
		}
	},

	// Convert dashed to camelCase; used by the css and data modules
	// Microsoft forgot to hump their vendor prefix (#9572)
	camelCase: function( string ) {
		return string.replace( rmsPrefix, "ms-" ).replace( rdashAlpha, fcamelCase );
	},

	nodeName: function( elem, name ) {
		return elem.nodeName && elem.nodeName.toLowerCase() === name.toLowerCase();
	},

	// args is for internal usage only
	each: function( obj, callback, args ) {
		var name,
			i = 0,
			length = obj.length,
			isObj = length === undefined || jQuery.isFunction( obj );

		if ( args ) {
			if ( isObj ) {
				for ( name in obj ) {
					if ( callback.apply( obj[ name ], args ) === false ) {
						break;
					}
				}
			} else {
				for ( ; i < length; ) {
					if ( callback.apply( obj[ i++ ], args ) === false ) {
						break;
					}
				}
			}

		// A special, fast, case for the most common use of each
		} else {
			if ( isObj ) {
				for ( name in obj ) {
					if ( callback.call( obj[ name ], name, obj[ name ] ) === false ) {
						break;
					}
				}
			} else {
				for ( ; i < length; ) {
					if ( callback.call( obj[ i ], i, obj[ i++ ] ) === false ) {
						break;
					}
				}
			}
		}

		return obj;
	},

	// Use native String.trim function wherever possible
	trim: core_trim && !core_trim.call("\uFEFF\xA0") ?
		function( text ) {
			return text == null ?
				"" :
				core_trim.call( text );
		} :

		// Otherwise use our own trimming functionality
		function( text ) {
			return text == null ?
				"" :
				( text + "" ).replace( rtrim, "" );
		},

	// results is for internal usage only
	makeArray: function( arr, results ) {
		var type,
			ret = results || [];

		if ( arr != null ) {
			// The window, strings (and functions) also have 'length'
			// Tweaked logic slightly to handle Blackberry 4.7 RegExp issues #6930
			type = jQuery.type( arr );

			if ( arr.length == null || type === "string" || type === "function" || type === "regexp" || jQuery.isWindow( arr ) ) {
				core_push.call( ret, arr );
			} else {
				jQuery.merge( ret, arr );
			}
		}

		return ret;
	},

	inArray: function( elem, arr, i ) {
		var len;

		if ( arr ) {
			if ( core_indexOf ) {
				return core_indexOf.call( arr, elem, i );
			}

			len = arr.length;
			i = i ? i < 0 ? Math.max( 0, len + i ) : i : 0;

			for ( ; i < len; i++ ) {
				// Skip accessing in sparse arrays
				if ( i in arr && arr[ i ] === elem ) {
					return i;
				}
			}
		}

		return -1;
	},

	merge: function( first, second ) {
		var l = second.length,
			i = first.length,
			j = 0;

		if ( typeof l === "number" ) {
			for ( ; j < l; j++ ) {
				first[ i++ ] = second[ j ];
			}

		} else {
			while ( second[j] !== undefined ) {
				first[ i++ ] = second[ j++ ];
			}
		}

		first.length = i;

		return first;
	},

	grep: function( elems, callback, inv ) {
		var retVal,
			ret = [],
			i = 0,
			length = elems.length;
		inv = !!inv;

		// Go through the array, only saving the items
		// that pass the validator function
		for ( ; i < length; i++ ) {
			retVal = !!callback( elems[ i ], i );
			if ( inv !== retVal ) {
				ret.push( elems[ i ] );
			}
		}

		return ret;
	},

	// arg is for internal usage only
	map: function( elems, callback, arg ) {
		var value, key,
			ret = [],
			i = 0,
			length = elems.length,
			// jquery objects are treated as arrays
			isArray = elems instanceof jQuery || length !== undefined && typeof length === "number" && ( ( length > 0 && elems[ 0 ] && elems[ length -1 ] ) || length === 0 || jQuery.isArray( elems ) ) ;

		// Go through the array, translating each of the items to their
		if ( isArray ) {
			for ( ; i < length; i++ ) {
				value = callback( elems[ i ], i, arg );

				if ( value != null ) {
					ret[ ret.length ] = value;
				}
			}

		// Go through every key on the object,
		} else {
			for ( key in elems ) {
				value = callback( elems[ key ], key, arg );

				if ( value != null ) {
					ret[ ret.length ] = value;
				}
			}
		}

		// Flatten any nested arrays
		return ret.concat.apply( [], ret );
	},

	// A global GUID counter for objects
	guid: 1,

	// Bind a function to a context, optionally partially applying any
	// arguments.
	proxy: function( fn, context ) {
		var tmp, args, proxy;

		if ( typeof context === "string" ) {
			tmp = fn[ context ];
			context = fn;
			fn = tmp;
		}

		// Quick check to determine if target is callable, in the spec
		// this throws a TypeError, but we will just return undefined.
		if ( !jQuery.isFunction( fn ) ) {
			return undefined;
		}

		// Simulated bind
		args = core_slice.call( arguments, 2 );
		proxy = function() {
			return fn.apply( context, args.concat( core_slice.call( arguments ) ) );
		};

		// Set the guid of unique handler to the same of original handler, so it can be removed
		proxy.guid = fn.guid = fn.guid || jQuery.guid++;

		return proxy;
	},

	// Multifunctional method to get and set values of a collection
	// The value/s can optionally be executed if it's a function
	access: function( elems, fn, key, value, chainable, emptyGet, pass ) {
		var exec,
			bulk = key == null,
			i = 0,
			length = elems.length;

		// Sets many values
		if ( key && typeof key === "object" ) {
			for ( i in key ) {
				jQuery.access( elems, fn, i, key[i], 1, emptyGet, value );
			}
			chainable = 1;

		// Sets one value
		} else if ( value !== undefined ) {
			// Optionally, function values get executed if exec is true
			exec = pass === undefined && jQuery.isFunction( value );

			if ( bulk ) {
				// Bulk operations only iterate when executing function values
				if ( exec ) {
					exec = fn;
					fn = function( elem, key, value ) {
						return exec.call( jQuery( elem ), value );
					};

				// Otherwise they run against the entire set
				} else {
					fn.call( elems, value );
					fn = null;
				}
			}

			if ( fn ) {
				for (; i < length; i++ ) {
					fn( elems[i], key, exec ? value.call( elems[i], i, fn( elems[i], key ) ) : value, pass );
				}
			}

			chainable = 1;
		}

		return chainable ?
			elems :

			// Gets
			bulk ?
				fn.call( elems ) :
				length ? fn( elems[0], key ) : emptyGet;
	},

	now: function() {
		return ( new Date() ).getTime();
	}
});

jQuery.ready.promise = function( obj ) {
	if ( !readyList ) {

		readyList = jQuery.Deferred();

		// Catch cases where $(document).ready() is called after the browser event has already occurred.
		// we once tried to use readyState "interactive" here, but it caused issues like the one
		// discovered by ChrisS here: http://bugs.jquery.com/ticket/12282#comment:15
		if ( document.readyState === "complete" ) {
			// Handle it asynchronously to allow scripts the opportunity to delay ready
			setTimeout( jQuery.ready, 1 );

		// Standards-based browsers support DOMContentLoaded
		} else if ( document.addEventListener ) {
			// Use the handy event callback
			document.addEventListener( "DOMContentLoaded", DOMContentLoaded, false );

			// A fallback to window.onload, that will always work
			window.addEventListener( "load", jQuery.ready, false );

		// If IE event model is used
		} else {
			// Ensure firing before onload, maybe late but safe also for iframes
			document.attachEvent( "onreadystatechange", DOMContentLoaded );

			// A fallback to window.onload, that will always work
			window.attachEvent( "onload", jQuery.ready );

			// If IE and not a frame
			// continually check to see if the document is ready
			var top = false;

			try {
				top = window.frameElement == null && document.documentElement;
			} catch(e) {}

			if ( top && top.doScroll ) {
				(function doScrollCheck() {
					if ( !jQuery.isReady ) {

						try {
							// Use the trick by Diego Perini
							// http://javascript.nwbox.com/IEContentLoaded/
							top.doScroll("left");
						} catch(e) {
							return setTimeout( doScrollCheck, 50 );
						}

						// and execute any waiting functions
						jQuery.ready();
					}
				})();
			}
		}
	}
	return readyList.promise( obj );
};

// Populate the class2type map
jQuery.each("Boolean Number String Function Array Date RegExp Object".split(" "), function(i, name) {
	class2type[ "[object " + name + "]" ] = name.toLowerCase();
});

// All jQuery objects should point back to these
rootjQuery = jQuery(document);
// String to Object options format cache
var optionsCache = {};

// Convert String-formatted options into Object-formatted ones and store in cache
function createOptions( options ) {
	var object = optionsCache[ options ] = {};
	jQuery.each( options.split( core_rspace ), function( _, flag ) {
		object[ flag ] = true;
	});
	return object;
}

/*
 * Create a callback list using the following parameters:
 *
 *	options: an optional list of space-separated options that will change how
 *			the callback list behaves or a more traditional option object
 *
 * By default a callback list will act like an event callback list and can be
 * "fired" multiple times.
 *
 * Possible options:
 *
 *	once:			will ensure the callback list can only be fired once (like a Deferred)
 *
 *	memory:			will keep track of previous values and will call any callback added
 *					after the list has been fired right away with the latest "memorized"
 *					values (like a Deferred)
 *
 *	unique:			will ensure a callback can only be added once (no duplicate in the list)
 *
 *	stopOnFalse:	interrupt callings when a callback returns false
 *
 */
jQuery.Callbacks = function( options ) {

	// Convert options from String-formatted to Object-formatted if needed
	// (we check in cache first)
	options = typeof options === "string" ?
		( optionsCache[ options ] || createOptions( options ) ) :
		jQuery.extend( {}, options );

	var // Last fire value (for non-forgettable lists)
		memory,
		// Flag to know if list was already fired
		fired,
		// Flag to know if list is currently firing
		firing,
		// First callback to fire (used internally by add and fireWith)
		firingStart,
		// End of the loop when firing
		firingLength,
		// Index of currently firing callback (modified by remove if needed)
		firingIndex,
		// Actual callback list
		list = [],
		// Stack of fire calls for repeatable lists
		stack = !options.once && [],
		// Fire callbacks
		fire = function( data ) {
			memory = options.memory && data;
			fired = true;
			firingIndex = firingStart || 0;
			firingStart = 0;
			firingLength = list.length;
			firing = true;
			for ( ; list && firingIndex < firingLength; firingIndex++ ) {
				if ( list[ firingIndex ].apply( data[ 0 ], data[ 1 ] ) === false && options.stopOnFalse ) {
					memory = false; // To prevent further calls using add
					break;
				}
			}
			firing = false;
			if ( list ) {
				if ( stack ) {
					if ( stack.length ) {
						fire( stack.shift() );
					}
				} else if ( memory ) {
					list = [];
				} else {
					self.disable();
				}
			}
		},
		// Actual Callbacks object
		self = {
			// Add a callback or a collection of callbacks to the list
			add: function() {
				if ( list ) {
					// First, we save the current length
					var start = list.length;
					(function add( args ) {
						jQuery.each( args, function( _, arg ) {
							var type = jQuery.type( arg );
							if ( type === "function" ) {
								if ( !options.unique || !self.has( arg ) ) {
									list.push( arg );
								}
							} else if ( arg && arg.length && type !== "string" ) {
								// Inspect recursively
								add( arg );
							}
						});
					})( arguments );
					// Do we need to add the callbacks to the
					// current firing batch?
					if ( firing ) {
						firingLength = list.length;
					// With memory, if we're not firing then
					// we should call right away
					} else if ( memory ) {
						firingStart = start;
						fire( memory );
					}
				}
				return this;
			},
			// Remove a callback from the list
			remove: function() {
				if ( list ) {
					jQuery.each( arguments, function( _, arg ) {
						var index;
						while( ( index = jQuery.inArray( arg, list, index ) ) > -1 ) {
							list.splice( index, 1 );
							// Handle firing indexes
							if ( firing ) {
								if ( index <= firingLength ) {
									firingLength--;
								}
								if ( index <= firingIndex ) {
									firingIndex--;
								}
							}
						}
					});
				}
				return this;
			},
			// Control if a given callback is in the list
			has: function( fn ) {
				return jQuery.inArray( fn, list ) > -1;
			},
			// Remove all callbacks from the list
			empty: function() {
				list = [];
				return this;
			},
			// Have the list do nothing anymore
			disable: function() {
				list = stack = memory = undefined;
				return this;
			},
			// Is it disabled?
			disabled: function() {
				return !list;
			},
			// Lock the list in its current state
			lock: function() {
				stack = undefined;
				if ( !memory ) {
					self.disable();
				}
				return this;
			},
			// Is it locked?
			locked: function() {
				return !stack;
			},
			// Call all callbacks with the given context and arguments
			fireWith: function( context, args ) {
				args = args || [];
				args = [ context, args.slice ? args.slice() : args ];
				if ( list && ( !fired || stack ) ) {
					if ( firing ) {
						stack.push( args );
					} else {
						fire( args );
					}
				}
				return this;
			},
			// Call all the callbacks with the given arguments
			fire: function() {
				self.fireWith( this, arguments );
				return this;
			},
			// To know if the callbacks have already been called at least once
			fired: function() {
				return !!fired;
			}
		};

	return self;
};
jQuery.extend({

	Deferred: function( func ) {
		var tuples = [
				// action, add listener, listener list, final state
				[ "resolve", "done", jQuery.Callbacks("once memory"), "resolved" ],
				[ "reject", "fail", jQuery.Callbacks("once memory"), "rejected" ],
				[ "notify", "progress", jQuery.Callbacks("memory") ]
			],
			state = "pending",
			promise = {
				state: function() {
					return state;
				},
				always: function() {
					deferred.done( arguments ).fail( arguments );
					return this;
				},
				then: function( /* fnDone, fnFail, fnProgress */ ) {
					var fns = arguments;
					return jQuery.Deferred(function( newDefer ) {
						jQuery.each( tuples, function( i, tuple ) {
							var action = tuple[ 0 ],
								fn = fns[ i ];
							// deferred[ done | fail | progress ] for forwarding actions to newDefer
							deferred[ tuple[1] ]( jQuery.isFunction( fn ) ?
								function() {
									var returned = fn.apply( this, arguments );
									if ( returned && jQuery.isFunction( returned.promise ) ) {
										returned.promise()
											.done( newDefer.resolve )
											.fail( newDefer.reject )
											.progress( newDefer.notify );
									} else {
										newDefer[ action + "With" ]( this === deferred ? newDefer : this, [ returned ] );
									}
								} :
								newDefer[ action ]
							);
						});
						fns = null;
					}).promise();
				},
				// Get a promise for this deferred
				// If obj is provided, the promise aspect is added to the object
				promise: function( obj ) {
					return obj != null ? jQuery.extend( obj, promise ) : promise;
				}
			},
			deferred = {};

		// Keep pipe for back-compat
		promise.pipe = promise.then;

		// Add list-specific methods
		jQuery.each( tuples, function( i, tuple ) {
			var list = tuple[ 2 ],
				stateString = tuple[ 3 ];

			// promise[ done | fail | progress ] = list.add
			promise[ tuple[1] ] = list.add;

			// Handle state
			if ( stateString ) {
				list.add(function() {
					// state = [ resolved | rejected ]
					state = stateString;

				// [ reject_list | resolve_list ].disable; progress_list.lock
				}, tuples[ i ^ 1 ][ 2 ].disable, tuples[ 2 ][ 2 ].lock );
			}

			// deferred[ resolve | reject | notify ] = list.fire
			deferred[ tuple[0] ] = list.fire;
			deferred[ tuple[0] + "With" ] = list.fireWith;
		});

		// Make the deferred a promise
		promise.promise( deferred );

		// Call given func if any
		if ( func ) {
			func.call( deferred, deferred );
		}

		// All done!
		return deferred;
	},

	// Deferred helper
	when: function( subordinate /* , ..., subordinateN */ ) {
		var i = 0,
			resolveValues = core_slice.call( arguments ),
			length = resolveValues.length,

			// the count of uncompleted subordinates
			remaining = length !== 1 || ( subordinate && jQuery.isFunction( subordinate.promise ) ) ? length : 0,

			// the master Deferred. If resolveValues consist of only a single Deferred, just use that.
			deferred = remaining === 1 ? subordinate : jQuery.Deferred(),

			// Update function for both resolve and progress values
			updateFunc = function( i, contexts, values ) {
				return function( value ) {
					contexts[ i ] = this;
					values[ i ] = arguments.length > 1 ? core_slice.call( arguments ) : value;
					if( values === progressValues ) {
						deferred.notifyWith( contexts, values );
					} else if ( !( --remaining ) ) {
						deferred.resolveWith( contexts, values );
					}
				};
			},

			progressValues, progressContexts, resolveContexts;

		// add listeners to Deferred subordinates; treat others as resolved
		if ( length > 1 ) {
			progressValues = new Array( length );
			progressContexts = new Array( length );
			resolveContexts = new Array( length );
			for ( ; i < length; i++ ) {
				if ( resolveValues[ i ] && jQuery.isFunction( resolveValues[ i ].promise ) ) {
					resolveValues[ i ].promise()
						.done( updateFunc( i, resolveContexts, resolveValues ) )
						.fail( deferred.reject )
						.progress( updateFunc( i, progressContexts, progressValues ) );
				} else {
					--remaining;
				}
			}
		}

		// if we're not waiting on anything, resolve the master
		if ( !remaining ) {
			deferred.resolveWith( resolveContexts, resolveValues );
		}

		return deferred.promise();
	}
});
jQuery.support = (function() {

	var support,
		all,
		a,
		select,
		opt,
		input,
		fragment,
		eventName,
		i,
		isSupported,
		clickFn,
		div = document.createElement("div");

	// Setup
	div.setAttribute( "className", "t" );
	div.innerHTML = "  <link/><table></table><a href='/a'>a</a><input type='checkbox'/>";

	// Support tests won't run in some limited or non-browser environments
	all = div.getElementsByTagName("*");
	a = div.getElementsByTagName("a")[ 0 ];
	if ( !all || !a || !all.length ) {
		return {};
	}

	// First batch of tests
	select = document.createElement("select");
	opt = select.appendChild( document.createElement("option") );
	input = div.getElementsByTagName("input")[ 0 ];

	a.style.cssText = "top:1px;float:left;opacity:.5";
	support = {
		// IE strips leading whitespace when .innerHTML is used
		leadingWhitespace: ( div.firstChild.nodeType === 3 ),

		// Make sure that tbody elements aren't automatically inserted
		// IE will insert them into empty tables
		tbody: !div.getElementsByTagName("tbody").length,

		// Make sure that link elements get serialized correctly by innerHTML
		// This requires a wrapper element in IE
		htmlSerialize: !!div.getElementsByTagName("link").length,

		// Get the style information from getAttribute
		// (IE uses .cssText instead)
		style: /top/.test( a.getAttribute("style") ),

		// Make sure that URLs aren't manipulated
		// (IE normalizes it by default)
		hrefNormalized: ( a.getAttribute("href") === "/a" ),

		// Make sure that element opacity exists
		// (IE uses filter instead)
		// Use a regex to work around a WebKit issue. See #5145
		opacity: /^0.5/.test( a.style.opacity ),

		// Verify style float existence
		// (IE uses styleFloat instead of cssFloat)
		cssFloat: !!a.style.cssFloat,

		// Make sure that if no value is specified for a checkbox
		// that it defaults to "on".
		// (WebKit defaults to "" instead)
		checkOn: ( input.value === "on" ),

		// Make sure that a selected-by-default option has a working selected property.
		// (WebKit defaults to false instead of true, IE too, if it's in an optgroup)
		optSelected: opt.selected,

		// Test setAttribute on camelCase class. If it works, we need attrFixes when doing get/setAttribute (ie6/7)
		getSetAttribute: div.className !== "t",

		// Tests for enctype support on a form (#6743)
		enctype: !!document.createElement("form").enctype,

		// Makes sure cloning an html5 element does not cause problems
		// Where outerHTML is undefined, this still works
		html5Clone: document.createElement("nav").cloneNode( true ).outerHTML !== "<:nav></:nav>",

		// jQuery.support.boxModel DEPRECATED in 1.8 since we don't support Quirks Mode
		boxModel: ( document.compatMode === "CSS1Compat" ),

		// Will be defined later
		submitBubbles: true,
		changeBubbles: true,
		focusinBubbles: false,
		deleteExpando: true,
		noCloneEvent: true,
		inlineBlockNeedsLayout: false,
		shrinkWrapBlocks: false,
		reliableMarginRight: true,
		boxSizingReliable: true,
		pixelPosition: false
	};

	// Make sure checked status is properly cloned
	input.checked = true;
	support.noCloneChecked = input.cloneNode( true ).checked;

	// Make sure that the options inside disabled selects aren't marked as disabled
	// (WebKit marks them as disabled)
	select.disabled = true;
	support.optDisabled = !opt.disabled;

	// Test to see if it's possible to delete an expando from an element
	// Fails in Internet Explorer
	try {
		delete div.test;
	} catch( e ) {
		support.deleteExpando = false;
	}

	if ( !div.addEventListener && div.attachEvent && div.fireEvent ) {
		div.attachEvent( "onclick", clickFn = function() {
			// Cloning a node shouldn't copy over any
			// bound event handlers (IE does this)
			support.noCloneEvent = false;
		});
		div.cloneNode( true ).fireEvent("onclick");
		div.detachEvent( "onclick", clickFn );
	}

	// Check if a radio maintains its value
	// after being appended to the DOM
	input = document.createElement("input");
	input.value = "t";
	input.setAttribute( "type", "radio" );
	support.radioValue = input.value === "t";

	input.setAttribute( "checked", "checked" );

	// #11217 - WebKit loses check when the name is after the checked attribute
	input.setAttribute( "name", "t" );

	div.appendChild( input );
	fragment = document.createDocumentFragment();
	fragment.appendChild( div.lastChild );

	// WebKit doesn't clone checked state correctly in fragments
	support.checkClone = fragment.cloneNode( true ).cloneNode( true ).lastChild.checked;

	// Check if a disconnected checkbox will retain its checked
	// value of true after appended to the DOM (IE6/7)
	support.appendChecked = input.checked;

	fragment.removeChild( input );
	fragment.appendChild( div );

	// Technique from Juriy Zaytsev
	// http://perfectionkills.com/detecting-event-support-without-browser-sniffing/
	// We only care about the case where non-standard event systems
	// are used, namely in IE. Short-circuiting here helps us to
	// avoid an eval call (in setAttribute) which can cause CSP
	// to go haywire. See: https://developer.mozilla.org/en/Security/CSP
	if ( div.attachEvent ) {
		for ( i in {
			submit: true,
			change: true,
			focusin: true
		}) {
			eventName = "on" + i;
			isSupported = ( eventName in div );
			if ( !isSupported ) {
				div.setAttribute( eventName, "return;" );
				isSupported = ( typeof div[ eventName ] === "function" );
			}
			support[ i + "Bubbles" ] = isSupported;
		}
	}

	// Run tests that need a body at doc ready
	jQuery(function() {
		var container, div, tds, marginDiv,
			divReset = "padding:0;margin:0;border:0;display:block;overflow:hidden;",
			body = document.getElementsByTagName("body")[0];

		if ( !body ) {
			// Return for frameset docs that don't have a body
			return;
		}

		container = document.createElement("div");
		container.style.cssText = "visibility:hidden;border:0;width:0;height:0;position:static;top:0;margin-top:1px";
		body.insertBefore( container, body.firstChild );

		// Construct the test element
		div = document.createElement("div");
		container.appendChild( div );

		// Check if table cells still have offsetWidth/Height when they are set
		// to display:none and there are still other visible table cells in a
		// table row; if so, offsetWidth/Height are not reliable for use when
		// determining if an element has been hidden directly using
		// display:none (it is still safe to use offsets if a parent element is
		// hidden; don safety goggles and see bug #4512 for more information).
		// (only IE 8 fails this test)
		div.innerHTML = "<table><tr><td></td><td>t</td></tr></table>";
		tds = div.getElementsByTagName("td");
		tds[ 0 ].style.cssText = "padding:0;margin:0;border:0;display:none";
		isSupported = ( tds[ 0 ].offsetHeight === 0 );

		tds[ 0 ].style.display = "";
		tds[ 1 ].style.display = "none";

		// Check if empty table cells still have offsetWidth/Height
		// (IE <= 8 fail this test)
		support.reliableHiddenOffsets = isSupported && ( tds[ 0 ].offsetHeight === 0 );

		// Check box-sizing and margin behavior
		div.innerHTML = "";
		div.style.cssText = "box-sizing:border-box;-moz-box-sizing:border-box;-webkit-box-sizing:border-box;padding:1px;border:1px;display:block;width:4px;margin-top:1%;position:absolute;top:1%;";
		support.boxSizing = ( div.offsetWidth === 4 );
		support.doesNotIncludeMarginInBodyOffset = ( body.offsetTop !== 1 );

		// NOTE: To any future maintainer, we've window.getComputedStyle
		// because jsdom on node.js will break without it.
		if ( window.getComputedStyle ) {
			support.pixelPosition = ( window.getComputedStyle( div, null ) || {} ).top !== "1%";
			support.boxSizingReliable = ( window.getComputedStyle( div, null ) || { width: "4px" } ).width === "4px";

			// Check if div with explicit width and no margin-right incorrectly
			// gets computed margin-right based on width of container. For more
			// info see bug #3333
			// Fails in WebKit before Feb 2011 nightlies
			// WebKit Bug 13343 - getComputedStyle returns wrong value for margin-right
			marginDiv = document.createElement("div");
			marginDiv.style.cssText = div.style.cssText = divReset;
			marginDiv.style.marginRight = marginDiv.style.width = "0";
			div.style.width = "1px";
			div.appendChild( marginDiv );
			support.reliableMarginRight =
				!parseFloat( ( window.getComputedStyle( marginDiv, null ) || {} ).marginRight );
		}

		if ( typeof div.style.zoom !== "undefined" ) {
			// Check if natively block-level elements act like inline-block
			// elements when setting their display to 'inline' and giving
			// them layout
			// (IE < 8 does this)
			div.innerHTML = "";
			div.style.cssText = divReset + "width:1px;padding:1px;display:inline;zoom:1";
			support.inlineBlockNeedsLayout = ( div.offsetWidth === 3 );

			// Check if elements with layout shrink-wrap their children
			// (IE 6 does this)
			div.style.display = "block";
			div.style.overflow = "visible";
			div.innerHTML = "<div></div>";
			div.firstChild.style.width = "5px";
			support.shrinkWrapBlocks = ( div.offsetWidth !== 3 );

			container.style.zoom = 1;
		}

		// Null elements to avoid leaks in IE
		body.removeChild( container );
		container = div = tds = marginDiv = null;
	});

	// Null elements to avoid leaks in IE
	fragment.removeChild( div );
	all = a = select = opt = input = fragment = div = null;

	return support;
})();
var rbrace = /(?:\{[\s\S]*\}|\[[\s\S]*\])$/,
	rmultiDash = /([A-Z])/g;

jQuery.extend({
	cache: {},

	deletedIds: [],

	// Remove at next major release (1.9/2.0)
	uuid: 0,

	// Unique for each copy of jQuery on the page
	// Non-digits removed to match rinlinejQuery
	expando: "jQuery" + ( jQuery.fn.jquery + Math.random() ).replace( /\D/g, "" ),

	// The following elements throw uncatchable exceptions if you
	// attempt to add expando properties to them.
	noData: {
		"embed": true,
		// Ban all objects except for Flash (which handle expandos)
		"object": "clsid:D27CDB6E-AE6D-11cf-96B8-444553540000",
		"applet": true
	},

	hasData: function( elem ) {
		elem = elem.nodeType ? jQuery.cache[ elem[jQuery.expando] ] : elem[ jQuery.expando ];
		return !!elem && !isEmptyDataObject( elem );
	},

	data: function( elem, name, data, pvt /* Internal Use Only */ ) {
		if ( !jQuery.acceptData( elem ) ) {
			return;
		}

		var thisCache, ret,
			internalKey = jQuery.expando,
			getByName = typeof name === "string",

			// We have to handle DOM nodes and JS objects differently because IE6-7
			// can't GC object references properly across the DOM-JS boundary
			isNode = elem.nodeType,

			// Only DOM nodes need the global jQuery cache; JS object data is
			// attached directly to the object so GC can occur automatically
			cache = isNode ? jQuery.cache : elem,

			// Only defining an ID for JS objects if its cache already exists allows
			// the code to shortcut on the same path as a DOM node with no cache
			id = isNode ? elem[ internalKey ] : elem[ internalKey ] && internalKey;

		// Avoid doing any more work than we need to when trying to get data on an
		// object that has no data at all
		if ( (!id || !cache[id] || (!pvt && !cache[id].data)) && getByName && data === undefined ) {
			return;
		}

		if ( !id ) {
			// Only DOM nodes need a new unique ID for each element since their data
			// ends up in the global cache
			if ( isNode ) {
				elem[ internalKey ] = id = jQuery.deletedIds.pop() || jQuery.guid++;
			} else {
				id = internalKey;
			}
		}

		if ( !cache[ id ] ) {
			cache[ id ] = {};

			// Avoids exposing jQuery metadata on plain JS objects when the object
			// is serialized using JSON.stringify
			if ( !isNode ) {
				cache[ id ].toJSON = jQuery.noop;
			}
		}

		// An object can be passed to jQuery.data instead of a key/value pair; this gets
		// shallow copied over onto the existing cache
		if ( typeof name === "object" || typeof name === "function" ) {
			if ( pvt ) {
				cache[ id ] = jQuery.extend( cache[ id ], name );
			} else {
				cache[ id ].data = jQuery.extend( cache[ id ].data, name );
			}
		}

		thisCache = cache[ id ];

		// jQuery data() is stored in a separate object inside the object's internal data
		// cache in order to avoid key collisions between internal data and user-defined
		// data.
		if ( !pvt ) {
			if ( !thisCache.data ) {
				thisCache.data = {};
			}

			thisCache = thisCache.data;
		}

		if ( data !== undefined ) {
			thisCache[ jQuery.camelCase( name ) ] = data;
		}

		// Check for both converted-to-camel and non-converted data property names
		// If a data property was specified
		if ( getByName ) {

			// First Try to find as-is property data
			ret = thisCache[ name ];

			// Test for null|undefined property data
			if ( ret == null ) {

				// Try to find the camelCased property
				ret = thisCache[ jQuery.camelCase( name ) ];
			}
		} else {
			ret = thisCache;
		}

		return ret;
	},

	removeData: function( elem, name, pvt /* Internal Use Only */ ) {
		if ( !jQuery.acceptData( elem ) ) {
			return;
		}

		var thisCache, i, l,

			isNode = elem.nodeType,

			// See jQuery.data for more information
			cache = isNode ? jQuery.cache : elem,
			id = isNode ? elem[ jQuery.expando ] : jQuery.expando;

		// If there is already no cache entry for this object, there is no
		// purpose in continuing
		if ( !cache[ id ] ) {
			return;
		}

		if ( name ) {

			thisCache = pvt ? cache[ id ] : cache[ id ].data;

			if ( thisCache ) {

				// Support array or space separated string names for data keys
				if ( !jQuery.isArray( name ) ) {

					// try the string as a key before any manipulation
					if ( name in thisCache ) {
						name = [ name ];
					} else {

						// split the camel cased version by spaces unless a key with the spaces exists
						name = jQuery.camelCase( name );
						if ( name in thisCache ) {
							name = [ name ];
						} else {
							name = name.split(" ");
						}
					}
				}

				for ( i = 0, l = name.length; i < l; i++ ) {
					delete thisCache[ name[i] ];
				}

				// If there is no data left in the cache, we want to continue
				// and let the cache object itself get destroyed
				if ( !( pvt ? isEmptyDataObject : jQuery.isEmptyObject )( thisCache ) ) {
					return;
				}
			}
		}

		// See jQuery.data for more information
		if ( !pvt ) {
			delete cache[ id ].data;

			// Don't destroy the parent cache unless the internal data object
			// had been the only thing left in it
			if ( !isEmptyDataObject( cache[ id ] ) ) {
				return;
			}
		}

		// Destroy the cache
		if ( isNode ) {
			jQuery.cleanData( [ elem ], true );

		// Use delete when supported for expandos or `cache` is not a window per isWindow (#10080)
		} else if ( jQuery.support.deleteExpando || cache != cache.window ) {
			delete cache[ id ];

		// When all else fails, null
		} else {
			cache[ id ] = null;
		}
	},

	// For internal use only.
	_data: function( elem, name, data ) {
		return jQuery.data( elem, name, data, true );
	},

	// A method for determining if a DOM node can handle the data expando
	acceptData: function( elem ) {
		var noData = elem.nodeName && jQuery.noData[ elem.nodeName.toLowerCase() ];

		// nodes accept data unless otherwise specified; rejection can be conditional
		return !noData || noData !== true && elem.getAttribute("classid") === noData;
	}
});

jQuery.fn.extend({
	data: function( key, value ) {
		var parts, part, attr, name, l,
			elem = this[0],
			i = 0,
			data = null;

		// Gets all values
		if ( key === undefined ) {
			if ( this.length ) {
				data = jQuery.data( elem );

				if ( elem.nodeType === 1 && !jQuery._data( elem, "parsedAttrs" ) ) {
					attr = elem.attributes;
					for ( l = attr.length; i < l; i++ ) {
						name = attr[i].name;

						if ( !name.indexOf( "data-" ) ) {
							name = jQuery.camelCase( name.substring(5) );

							dataAttr( elem, name, data[ name ] );
						}
					}
					jQuery._data( elem, "parsedAttrs", true );
				}
			}

			return data;
		}

		// Sets multiple values
		if ( typeof key === "object" ) {
			return this.each(function() {
				jQuery.data( this, key );
			});
		}

		parts = key.split( ".", 2 );
		parts[1] = parts[1] ? "." + parts[1] : "";
		part = parts[1] + "!";

		return jQuery.access( this, function( value ) {

			if ( value === undefined ) {
				data = this.triggerHandler( "getData" + part, [ parts[0] ] );

				// Try to fetch any internally stored data first
				if ( data === undefined && elem ) {
					data = jQuery.data( elem, key );
					data = dataAttr( elem, key, data );
				}

				return data === undefined && parts[1] ?
					this.data( parts[0] ) :
					data;
			}

			parts[1] = value;
			this.each(function() {
				var self = jQuery( this );

				self.triggerHandler( "setData" + part, parts );
				jQuery.data( this, key, value );
				self.triggerHandler( "changeData" + part, parts );
			});
		}, null, value, arguments.length > 1, null, false );
	},

	removeData: function( key ) {
		return this.each(function() {
			jQuery.removeData( this, key );
		});
	}
});

function dataAttr( elem, key, data ) {
	// If nothing was found internally, try to fetch any
	// data from the HTML5 data-* attribute
	if ( data === undefined && elem.nodeType === 1 ) {

		var name = "data-" + key.replace( rmultiDash, "-$1" ).toLowerCase();

		data = elem.getAttribute( name );

		if ( typeof data === "string" ) {
			try {
				data = data === "true" ? true :
				data === "false" ? false :
				data === "null" ? null :
				// Only convert to a number if it doesn't change the string
				+data + "" === data ? +data :
				rbrace.test( data ) ? jQuery.parseJSON( data ) :
					data;
			} catch( e ) {}

			// Make sure we set the data so it isn't changed later
			jQuery.data( elem, key, data );

		} else {
			data = undefined;
		}
	}

	return data;
}

// checks a cache object for emptiness
function isEmptyDataObject( obj ) {
	var name;
	for ( name in obj ) {

		// if the public data object is empty, the private is still empty
		if ( name === "data" && jQuery.isEmptyObject( obj[name] ) ) {
			continue;
		}
		if ( name !== "toJSON" ) {
			return false;
		}
	}

	return true;
}
jQuery.extend({
	queue: function( elem, type, data ) {
		var queue;

		if ( elem ) {
			type = ( type || "fx" ) + "queue";
			queue = jQuery._data( elem, type );

			// Speed up dequeue by getting out quickly if this is just a lookup
			if ( data ) {
				if ( !queue || jQuery.isArray(data) ) {
					queue = jQuery._data( elem, type, jQuery.makeArray(data) );
				} else {
					queue.push( data );
				}
			}
			return queue || [];
		}
	},

	dequeue: function( elem, type ) {
		type = type || "fx";

		var queue = jQuery.queue( elem, type ),
			startLength = queue.length,
			fn = queue.shift(),
			hooks = jQuery._queueHooks( elem, type ),
			next = function() {
				jQuery.dequeue( elem, type );
			};

		// If the fx queue is dequeued, always remove the progress sentinel
		if ( fn === "inprogress" ) {
			fn = queue.shift();
			startLength--;
		}

		if ( fn ) {

			// Add a progress sentinel to prevent the fx queue from being
			// automatically dequeued
			if ( type === "fx" ) {
				queue.unshift( "inprogress" );
			}

			// clear up the last queue stop function
			delete hooks.stop;
			fn.call( elem, next, hooks );
		}

		if ( !startLength && hooks ) {
			hooks.empty.fire();
		}
	},

	// not intended for public consumption - generates a queueHooks object, or returns the current one
	_queueHooks: function( elem, type ) {
		var key = type + "queueHooks";
		return jQuery._data( elem, key ) || jQuery._data( elem, key, {
			empty: jQuery.Callbacks("once memory").add(function() {
				jQuery.removeData( elem, type + "queue", true );
				jQuery.removeData( elem, key, true );
			})
		});
	}
});

jQuery.fn.extend({
	queue: function( type, data ) {
		var setter = 2;

		if ( typeof type !== "string" ) {
			data = type;
			type = "fx";
			setter--;
		}

		if ( arguments.length < setter ) {
			return jQuery.queue( this[0], type );
		}

		return data === undefined ?
			this :
			this.each(function() {
				var queue = jQuery.queue( this, type, data );

				// ensure a hooks for this queue
				jQuery._queueHooks( this, type );

				if ( type === "fx" && queue[0] !== "inprogress" ) {
					jQuery.dequeue( this, type );
				}
			});
	},
	dequeue: function( type ) {
		return this.each(function() {
			jQuery.dequeue( this, type );
		});
	},
	// Based off of the plugin by Clint Helfers, with permission.
	// http://blindsignals.com/index.php/2009/07/jquery-delay/
	delay: function( time, type ) {
		time = jQuery.fx ? jQuery.fx.speeds[ time ] || time : time;
		type = type || "fx";

		return this.queue( type, function( next, hooks ) {
			var timeout = setTimeout( next, time );
			hooks.stop = function() {
				clearTimeout( timeout );
			};
		});
	},
	clearQueue: function( type ) {
		return this.queue( type || "fx", [] );
	},
	// Get a promise resolved when queues of a certain type
	// are emptied (fx is the type by default)
	promise: function( type, obj ) {
		var tmp,
			count = 1,
			defer = jQuery.Deferred(),
			elements = this,
			i = this.length,
			resolve = function() {
				if ( !( --count ) ) {
					defer.resolveWith( elements, [ elements ] );
				}
			};

		if ( typeof type !== "string" ) {
			obj = type;
			type = undefined;
		}
		type = type || "fx";

		while( i-- ) {
			tmp = jQuery._data( elements[ i ], type + "queueHooks" );
			if ( tmp && tmp.empty ) {
				count++;
				tmp.empty.add( resolve );
			}
		}
		resolve();
		return defer.promise( obj );
	}
});
var nodeHook, boolHook, fixSpecified,
	rclass = /[\t\r\n]/g,
	rreturn = /\r/g,
	rtype = /^(?:button|input)$/i,
	rfocusable = /^(?:button|input|object|select|textarea)$/i,
	rclickable = /^a(?:rea|)$/i,
	rboolean = /^(?:autofocus|autoplay|async|checked|controls|defer|disabled|hidden|loop|multiple|open|readonly|required|scoped|selected)$/i,
	getSetAttribute = jQuery.support.getSetAttribute;

jQuery.fn.extend({
	attr: function( name, value ) {
		return jQuery.access( this, jQuery.attr, name, value, arguments.length > 1 );
	},

	removeAttr: function( name ) {
		return this.each(function() {
			jQuery.removeAttr( this, name );
		});
	},

	prop: function( name, value ) {
		return jQuery.access( this, jQuery.prop, name, value, arguments.length > 1 );
	},

	removeProp: function( name ) {
		name = jQuery.propFix[ name ] || name;
		return this.each(function() {
			// try/catch handles cases where IE balks (such as removing a property on window)
			try {
				this[ name ] = undefined;
				delete this[ name ];
			} catch( e ) {}
		});
	},

	addClass: function( value ) {
		var classNames, i, l, elem,
			setClass, c, cl;

		if ( jQuery.isFunction( value ) ) {
			return this.each(function( j ) {
				jQuery( this ).addClass( value.call(this, j, this.className) );
			});
		}

		if ( value && typeof value === "string" ) {
			classNames = value.split( core_rspace );

			for ( i = 0, l = this.length; i < l; i++ ) {
				elem = this[ i ];

				if ( elem.nodeType === 1 ) {
					if ( !elem.className && classNames.length === 1 ) {
						elem.className = value;

					} else {
						setClass = " " + elem.className + " ";

						for ( c = 0, cl = classNames.length; c < cl; c++ ) {
							if ( setClass.indexOf( " " + classNames[ c ] + " " ) < 0 ) {
								setClass += classNames[ c ] + " ";
							}
						}
						elem.className = jQuery.trim( setClass );
					}
				}
			}
		}

		return this;
	},

	removeClass: function( value ) {
		var removes, className, elem, c, cl, i, l;

		if ( jQuery.isFunction( value ) ) {
			return this.each(function( j ) {
				jQuery( this ).removeClass( value.call(this, j, this.className) );
			});
		}
		if ( (value && typeof value === "string") || value === undefined ) {
			removes = ( value || "" ).split( core_rspace );

			for ( i = 0, l = this.length; i < l; i++ ) {
				elem = this[ i ];
				if ( elem.nodeType === 1 && elem.className ) {

					className = (" " + elem.className + " ").replace( rclass, " " );

					// loop over each item in the removal list
					for ( c = 0, cl = removes.length; c < cl; c++ ) {
						// Remove until there is nothing to remove,
						while ( className.indexOf(" " + removes[ c ] + " ") >= 0 ) {
							className = className.replace( " " + removes[ c ] + " " , " " );
						}
					}
					elem.className = value ? jQuery.trim( className ) : "";
				}
			}
		}

		return this;
	},

	toggleClass: function( value, stateVal ) {
		var type = typeof value,
			isBool = typeof stateVal === "boolean";

		if ( jQuery.isFunction( value ) ) {
			return this.each(function( i ) {
				jQuery( this ).toggleClass( value.call(this, i, this.className, stateVal), stateVal );
			});
		}

		return this.each(function() {
			if ( type === "string" ) {
				// toggle individual class names
				var className,
					i = 0,
					self = jQuery( this ),
					state = stateVal,
					classNames = value.split( core_rspace );

				while ( (className = classNames[ i++ ]) ) {
					// check each className given, space separated list
					state = isBool ? state : !self.hasClass( className );
					self[ state ? "addClass" : "removeClass" ]( className );
				}

			} else if ( type === "undefined" || type === "boolean" ) {
				if ( this.className ) {
					// store className if set
					jQuery._data( this, "__className__", this.className );
				}

				// toggle whole className
				this.className = this.className || value === false ? "" : jQuery._data( this, "__className__" ) || "";
			}
		});
	},

	hasClass: function( selector ) {
		var className = " " + selector + " ",
			i = 0,
			l = this.length;
		for ( ; i < l; i++ ) {
			if ( this[i].nodeType === 1 && (" " + this[i].className + " ").replace(rclass, " ").indexOf( className ) >= 0 ) {
				return true;
			}
		}

		return false;
	},

	val: function( value ) {
		var hooks, ret, isFunction,
			elem = this[0];

		if ( !arguments.length ) {
			if ( elem ) {
				hooks = jQuery.valHooks[ elem.type ] || jQuery.valHooks[ elem.nodeName.toLowerCase() ];

				if ( hooks && "get" in hooks && (ret = hooks.get( elem, "value" )) !== undefined ) {
					return ret;
				}

				ret = elem.value;

				return typeof ret === "string" ?
					// handle most common string cases
					ret.replace(rreturn, "") :
					// handle cases where value is null/undef or number
					ret == null ? "" : ret;
			}

			return;
		}

		isFunction = jQuery.isFunction( value );

		return this.each(function( i ) {
			var val,
				self = jQuery(this);

			if ( this.nodeType !== 1 ) {
				return;
			}

			if ( isFunction ) {
				val = value.call( this, i, self.val() );
			} else {
				val = value;
			}

			// Treat null/undefined as ""; convert numbers to string
			if ( val == null ) {
				val = "";
			} else if ( typeof val === "number" ) {
				val += "";
			} else if ( jQuery.isArray( val ) ) {
				val = jQuery.map(val, function ( value ) {
					return value == null ? "" : value + "";
				});
			}

			hooks = jQuery.valHooks[ this.type ] || jQuery.valHooks[ this.nodeName.toLowerCase() ];

			// If set returns undefined, fall back to normal setting
			if ( !hooks || !("set" in hooks) || hooks.set( this, val, "value" ) === undefined ) {
				this.value = val;
			}
		});
	}
});

jQuery.extend({
	valHooks: {
		option: {
			get: function( elem ) {
				// attributes.value is undefined in Blackberry 4.7 but
				// uses .value. See #6932
				var val = elem.attributes.value;
				return !val || val.specified ? elem.value : elem.text;
			}
		},
		select: {
			get: function( elem ) {
				var value, option,
					options = elem.options,
					index = elem.selectedIndex,
					one = elem.type === "select-one" || index < 0,
					values = one ? null : [],
					max = one ? index + 1 : options.length,
					i = index < 0 ?
						max :
						one ? index : 0;

				// Loop through all the selected options
				for ( ; i < max; i++ ) {
					option = options[ i ];

					// oldIE doesn't update selected after form reset (#2551)
					if ( ( option.selected || i === index ) &&
							// Don't return options that are disabled or in a disabled optgroup
							( jQuery.support.optDisabled ? !option.disabled : option.getAttribute("disabled") === null ) &&
							( !option.parentNode.disabled || !jQuery.nodeName( option.parentNode, "optgroup" ) ) ) {

						// Get the specific value for the option
						value = jQuery( option ).val();

						// We don't need an array for one selects
						if ( one ) {
							return value;
						}

						// Multi-Selects return an array
						values.push( value );
					}
				}

				return values;
			},

			set: function( elem, value ) {
				var values = jQuery.makeArray( value );

				jQuery(elem).find("option").each(function() {
					this.selected = jQuery.inArray( jQuery(this).val(), values ) >= 0;
				});

				if ( !values.length ) {
					elem.selectedIndex = -1;
				}
				return values;
			}
		}
	},

	// Unused in 1.8, left in so attrFn-stabbers won't die; remove in 1.9
	attrFn: {},

	attr: function( elem, name, value, pass ) {
		var ret, hooks, notxml,
			nType = elem.nodeType;

		// don't get/set attributes on text, comment and attribute nodes
		if ( !elem || nType === 3 || nType === 8 || nType === 2 ) {
			return;
		}

		if ( pass && jQuery.isFunction( jQuery.fn[ name ] ) ) {
			return jQuery( elem )[ name ]( value );
		}

		// Fallback to prop when attributes are not supported
		if ( typeof elem.getAttribute === "undefined" ) {
			return jQuery.prop( elem, name, value );
		}

		notxml = nType !== 1 || !jQuery.isXMLDoc( elem );

		// All attributes are lowercase
		// Grab necessary hook if one is defined
		if ( notxml ) {
			name = name.toLowerCase();
			hooks = jQuery.attrHooks[ name ] || ( rboolean.test( name ) ? boolHook : nodeHook );
		}

		if ( value !== undefined ) {

			if ( value === null ) {
				jQuery.removeAttr( elem, name );
				return;

			} else if ( hooks && "set" in hooks && notxml && (ret = hooks.set( elem, value, name )) !== undefined ) {
				return ret;

			} else {
				elem.setAttribute( name, value + "" );
				return value;
			}

		} else if ( hooks && "get" in hooks && notxml && (ret = hooks.get( elem, name )) !== null ) {
			return ret;

		} else {

			ret = elem.getAttribute( name );

			// Non-existent attributes return null, we normalize to undefined
			return ret === null ?
				undefined :
				ret;
		}
	},

	removeAttr: function( elem, value ) {
		var propName, attrNames, name, isBool,
			i = 0;

		if ( value && elem.nodeType === 1 ) {

			attrNames = value.split( core_rspace );

			for ( ; i < attrNames.length; i++ ) {
				name = attrNames[ i ];

				if ( name ) {
					propName = jQuery.propFix[ name ] || name;
					isBool = rboolean.test( name );

					// See #9699 for explanation of this approach (setting first, then removal)
					// Do not do this for boolean attributes (see #10870)
					if ( !isBool ) {
						jQuery.attr( elem, name, "" );
					}
					elem.removeAttribute( getSetAttribute ? name : propName );

					// Set corresponding property to false for boolean attributes
					if ( isBool && propName in elem ) {
						elem[ propName ] = false;
					}
				}
			}
		}
	},

	attrHooks: {
		type: {
			set: function( elem, value ) {
				// We can't allow the type property to be changed (since it causes problems in IE)
				if ( rtype.test( elem.nodeName ) && elem.parentNode ) {
					jQuery.error( "type property can't be changed" );
				} else if ( !jQuery.support.radioValue && value === "radio" && jQuery.nodeName(elem, "input") ) {
					// Setting the type on a radio button after the value resets the value in IE6-9
					// Reset value to it's default in case type is set after value
					// This is for element creation
					var val = elem.value;
					elem.setAttribute( "type", value );
					if ( val ) {
						elem.value = val;
					}
					return value;
				}
			}
		},
		// Use the value property for back compat
		// Use the nodeHook for button elements in IE6/7 (#1954)
		value: {
			get: function( elem, name ) {
				if ( nodeHook && jQuery.nodeName( elem, "button" ) ) {
					return nodeHook.get( elem, name );
				}
				return name in elem ?
					elem.value :
					null;
			},
			set: function( elem, value, name ) {
				if ( nodeHook && jQuery.nodeName( elem, "button" ) ) {
					return nodeHook.set( elem, value, name );
				}
				// Does not return so that setAttribute is also used
				elem.value = value;
			}
		}
	},

	propFix: {
		tabindex: "tabIndex",
		readonly: "readOnly",
		"for": "htmlFor",
		"class": "className",
		maxlength: "maxLength",
		cellspacing: "cellSpacing",
		cellpadding: "cellPadding",
		rowspan: "rowSpan",
		colspan: "colSpan",
		usemap: "useMap",
		frameborder: "frameBorder",
		contenteditable: "contentEditable"
	},

	prop: function( elem, name, value ) {
		var ret, hooks, notxml,
			nType = elem.nodeType;

		// don't get/set properties on text, comment and attribute nodes
		if ( !elem || nType === 3 || nType === 8 || nType === 2 ) {
			return;
		}

		notxml = nType !== 1 || !jQuery.isXMLDoc( elem );

		if ( notxml ) {
			// Fix name and attach hooks
			name = jQuery.propFix[ name ] || name;
			hooks = jQuery.propHooks[ name ];
		}

		if ( value !== undefined ) {
			if ( hooks && "set" in hooks && (ret = hooks.set( elem, value, name )) !== undefined ) {
				return ret;

			} else {
				return ( elem[ name ] = value );
			}

		} else {
			if ( hooks && "get" in hooks && (ret = hooks.get( elem, name )) !== null ) {
				return ret;

			} else {
				return elem[ name ];
			}
		}
	},

	propHooks: {
		tabIndex: {
			get: function( elem ) {
				// elem.tabIndex doesn't always return the correct value when it hasn't been explicitly set
				// http://fluidproject.org/blog/2008/01/09/getting-setting-and-removing-tabindex-values-with-javascript/
				var attributeNode = elem.getAttributeNode("tabindex");

				return attributeNode && attributeNode.specified ?
					parseInt( attributeNode.value, 10 ) :
					rfocusable.test( elem.nodeName ) || rclickable.test( elem.nodeName ) && elem.href ?
						0 :
						undefined;
			}
		}
	}
});

// Hook for boolean attributes
boolHook = {
	get: function( elem, name ) {
		// Align boolean attributes with corresponding properties
		// Fall back to attribute presence where some booleans are not supported
		var attrNode,
			property = jQuery.prop( elem, name );
		return property === true || typeof property !== "boolean" && ( attrNode = elem.getAttributeNode(name) ) && attrNode.nodeValue !== false ?
			name.toLowerCase() :
			undefined;
	},
	set: function( elem, value, name ) {
		var propName;
		if ( value === false ) {
			// Remove boolean attributes when set to false
			jQuery.removeAttr( elem, name );
		} else {
			// value is true since we know at this point it's type boolean and not false
			// Set boolean attributes to the same name and set the DOM property
			propName = jQuery.propFix[ name ] || name;
			if ( propName in elem ) {
				// Only set the IDL specifically if it already exists on the element
				elem[ propName ] = true;
			}

			elem.setAttribute( name, name.toLowerCase() );
		}
		return name;
	}
};

// IE6/7 do not support getting/setting some attributes with get/setAttribute
if ( !getSetAttribute ) {

	fixSpecified = {
		name: true,
		id: true,
		coords: true
	};

	// Use this for any attribute in IE6/7
	// This fixes almost every IE6/7 issue
	nodeHook = jQuery.valHooks.button = {
		get: function( elem, name ) {
			var ret;
			ret = elem.getAttributeNode( name );
			return ret && ( fixSpecified[ name ] ? ret.value !== "" : ret.specified ) ?
				ret.value :
				undefined;
		},
		set: function( elem, value, name ) {
			// Set the existing or create a new attribute node
			var ret = elem.getAttributeNode( name );
			if ( !ret ) {
				ret = document.createAttribute( name );
				elem.setAttributeNode( ret );
			}
			return ( ret.value = value + "" );
		}
	};

	// Set width and height to auto instead of 0 on empty string( Bug #8150 )
	// This is for removals
	jQuery.each([ "width", "height" ], function( i, name ) {
		jQuery.attrHooks[ name ] = jQuery.extend( jQuery.attrHooks[ name ], {
			set: function( elem, value ) {
				if ( value === "" ) {
					elem.setAttribute( name, "auto" );
					return value;
				}
			}
		});
	});

	// Set contenteditable to false on removals(#10429)
	// Setting to empty string throws an error as an invalid value
	jQuery.attrHooks.contenteditable = {
		get: nodeHook.get,
		set: function( elem, value, name ) {
			if ( value === "" ) {
				value = "false";
			}
			nodeHook.set( elem, value, name );
		}
	};
}


// Some attributes require a special call on IE
if ( !jQuery.support.hrefNormalized ) {
	jQuery.each([ "href", "src", "width", "height" ], function( i, name ) {
		jQuery.attrHooks[ name ] = jQuery.extend( jQuery.attrHooks[ name ], {
			get: function( elem ) {
				var ret = elem.getAttribute( name, 2 );
				return ret === null ? undefined : ret;
			}
		});
	});
}

if ( !jQuery.support.style ) {
	jQuery.attrHooks.style = {
		get: function( elem ) {
			// Return undefined in the case of empty string
			// Normalize to lowercase since IE uppercases css property names
			return elem.style.cssText.toLowerCase() || undefined;
		},
		set: function( elem, value ) {
			return ( elem.style.cssText = value + "" );
		}
	};
}

// Safari mis-reports the default selected property of an option
// Accessing the parent's selectedIndex property fixes it
if ( !jQuery.support.optSelected ) {
	jQuery.propHooks.selected = jQuery.extend( jQuery.propHooks.selected, {
		get: function( elem ) {
			var parent = elem.parentNode;

			if ( parent ) {
				parent.selectedIndex;

				// Make sure that it also works with optgroups, see #5701
				if ( parent.parentNode ) {
					parent.parentNode.selectedIndex;
				}
			}
			return null;
		}
	});
}

// IE6/7 call enctype encoding
if ( !jQuery.support.enctype ) {
	jQuery.propFix.enctype = "encoding";
}

// Radios and checkboxes getter/setter
if ( !jQuery.support.checkOn ) {
	jQuery.each([ "radio", "checkbox" ], function() {
		jQuery.valHooks[ this ] = {
			get: function( elem ) {
				// Handle the case where in Webkit "" is returned instead of "on" if a value isn't specified
				return elem.getAttribute("value") === null ? "on" : elem.value;
			}
		};
	});
}
jQuery.each([ "radio", "checkbox" ], function() {
	jQuery.valHooks[ this ] = jQuery.extend( jQuery.valHooks[ this ], {
		set: function( elem, value ) {
			if ( jQuery.isArray( value ) ) {
				return ( elem.checked = jQuery.inArray( jQuery(elem).val(), value ) >= 0 );
			}
		}
	});
});
var rformElems = /^(?:textarea|input|select)$/i,
	rtypenamespace = /^([^\.]*|)(?:\.(.+)|)$/,
	rhoverHack = /(?:^|\s)hover(\.\S+|)\b/,
	rkeyEvent = /^key/,
	rmouseEvent = /^(?:mouse|contextmenu)|click/,
	rfocusMorph = /^(?:focusinfocus|focusoutblur)$/,
	hoverHack = function( events ) {
		return jQuery.event.special.hover ? events : events.replace( rhoverHack, "mouseenter$1 mouseleave$1" );
	};

/*
 * Helper functions for managing events -- not part of the public interface.
 * Props to Dean Edwards' addEvent library for many of the ideas.
 */
jQuery.event = {

	add: function( elem, types, handler, data, selector ) {

		var elemData, eventHandle, events,
			t, tns, type, namespaces, handleObj,
			handleObjIn, handlers, special;

		// Don't attach events to noData or text/comment nodes (allow plain objects tho)
		if ( elem.nodeType === 3 || elem.nodeType === 8 || !types || !handler || !(elemData = jQuery._data( elem )) ) {
			return;
		}

		// Caller can pass in an object of custom data in lieu of the handler
		if ( handler.handler ) {
			handleObjIn = handler;
			handler = handleObjIn.handler;
			selector = handleObjIn.selector;
		}

		// Make sure that the handler has a unique ID, used to find/remove it later
		if ( !handler.guid ) {
			handler.guid = jQuery.guid++;
		}

		// Init the element's event structure and main handler, if this is the first
		events = elemData.events;
		if ( !events ) {
			elemData.events = events = {};
		}
		eventHandle = elemData.handle;
		if ( !eventHandle ) {
			elemData.handle = eventHandle = function( e ) {
				// Discard the second event of a jQuery.event.trigger() and
				// when an event is called after a page has unloaded
				return typeof jQuery !== "undefined" && (!e || jQuery.event.triggered !== e.type) ?
					jQuery.event.dispatch.apply( eventHandle.elem, arguments ) :
					undefined;
			};
			// Add elem as a property of the handle fn to prevent a memory leak with IE non-native events
			eventHandle.elem = elem;
		}

		// Handle multiple events separated by a space
		// jQuery(...).bind("mouseover mouseout", fn);
		types = jQuery.trim( hoverHack(types) ).split( " " );
		for ( t = 0; t < types.length; t++ ) {

			tns = rtypenamespace.exec( types[t] ) || [];
			type = tns[1];
			namespaces = ( tns[2] || "" ).split( "." ).sort();

			// If event changes its type, use the special event handlers for the changed type
			special = jQuery.event.special[ type ] || {};

			// If selector defined, determine special event api type, otherwise given type
			type = ( selector ? special.delegateType : special.bindType ) || type;

			// Update special based on newly reset type
			special = jQuery.event.special[ type ] || {};

			// handleObj is passed to all event handlers
			handleObj = jQuery.extend({
				type: type,
				origType: tns[1],
				data: data,
				handler: handler,
				guid: handler.guid,
				selector: selector,
				needsContext: selector && jQuery.expr.match.needsContext.test( selector ),
				namespace: namespaces.join(".")
			}, handleObjIn );

			// Init the event handler queue if we're the first
			handlers = events[ type ];
			if ( !handlers ) {
				handlers = events[ type ] = [];
				handlers.delegateCount = 0;

				// Only use addEventListener/attachEvent if the special events handler returns false
				if ( !special.setup || special.setup.call( elem, data, namespaces, eventHandle ) === false ) {
					// Bind the global event handler to the element
					if ( elem.addEventListener ) {
						elem.addEventListener( type, eventHandle, false );

					} else if ( elem.attachEvent ) {
						elem.attachEvent( "on" + type, eventHandle );
					}
				}
			}

			if ( special.add ) {
				special.add.call( elem, handleObj );

				if ( !handleObj.handler.guid ) {
					handleObj.handler.guid = handler.guid;
				}
			}

			// Add to the element's handler list, delegates in front
			if ( selector ) {
				handlers.splice( handlers.delegateCount++, 0, handleObj );
			} else {
				handlers.push( handleObj );
			}

			// Keep track of which events have ever been used, for event optimization
			jQuery.event.global[ type ] = true;
		}

		// Nullify elem to prevent memory leaks in IE
		elem = null;
	},

	global: {},

	// Detach an event or set of events from an element
	remove: function( elem, types, handler, selector, mappedTypes ) {

		var t, tns, type, origType, namespaces, origCount,
			j, events, special, eventType, handleObj,
			elemData = jQuery.hasData( elem ) && jQuery._data( elem );

		if ( !elemData || !(events = elemData.events) ) {
			return;
		}

		// Once for each type.namespace in types; type may be omitted
		types = jQuery.trim( hoverHack( types || "" ) ).split(" ");
		for ( t = 0; t < types.length; t++ ) {
			tns = rtypenamespace.exec( types[t] ) || [];
			type = origType = tns[1];
			namespaces = tns[2];

			// Unbind all events (on this namespace, if provided) for the element
			if ( !type ) {
				for ( type in events ) {
					jQuery.event.remove( elem, type + types[ t ], handler, selector, true );
				}
				continue;
			}

			special = jQuery.event.special[ type ] || {};
			type = ( selector? special.delegateType : special.bindType ) || type;
			eventType = events[ type ] || [];
			origCount = eventType.length;
			namespaces = namespaces ? new RegExp("(^|\\.)" + namespaces.split(".").sort().join("\\.(?:.*\\.|)") + "(\\.|$)") : null;

			// Remove matching events
			for ( j = 0; j < eventType.length; j++ ) {
				handleObj = eventType[ j ];

				if ( ( mappedTypes || origType === handleObj.origType ) &&
					 ( !handler || handler.guid === handleObj.guid ) &&
					 ( !namespaces || namespaces.test( handleObj.namespace ) ) &&
					 ( !selector || selector === handleObj.selector || selector === "**" && handleObj.selector ) ) {
					eventType.splice( j--, 1 );

					if ( handleObj.selector ) {
						eventType.delegateCount--;
					}
					if ( special.remove ) {
						special.remove.call( elem, handleObj );
					}
				}
			}

			// Remove generic event handler if we removed something and no more handlers exist
			// (avoids potential for endless recursion during removal of special event handlers)
			if ( eventType.length === 0 && origCount !== eventType.length ) {
				if ( !special.teardown || special.teardown.call( elem, namespaces, elemData.handle ) === false ) {
					jQuery.removeEvent( elem, type, elemData.handle );
				}

				delete events[ type ];
			}
		}

		// Remove the expando if it's no longer used
		if ( jQuery.isEmptyObject( events ) ) {
			delete elemData.handle;

			// removeData also checks for emptiness and clears the expando if empty
			// so use it instead of delete
			jQuery.removeData( elem, "events", true );
		}
	},

	// Events that are safe to short-circuit if no handlers are attached.
	// Native DOM events should not be added, they may have inline handlers.
	customEvent: {
		"getData": true,
		"setData": true,
		"changeData": true
	},

	trigger: function( event, data, elem, onlyHandlers ) {
		// Don't do events on text and comment nodes
		if ( elem && (elem.nodeType === 3 || elem.nodeType === 8) ) {
			return;
		}

		// Event object or event type
		var cache, exclusive, i, cur, old, ontype, special, handle, eventPath, bubbleType,
			type = event.type || event,
			namespaces = [];

		// focus/blur morphs to focusin/out; ensure we're not firing them right now
		if ( rfocusMorph.test( type + jQuery.event.triggered ) ) {
			return;
		}

		if ( type.indexOf( "!" ) >= 0 ) {
			// Exclusive events trigger only for the exact event (no namespaces)
			type = type.slice(0, -1);
			exclusive = true;
		}

		if ( type.indexOf( "." ) >= 0 ) {
			// Namespaced trigger; create a regexp to match event type in handle()
			namespaces = type.split(".");
			type = namespaces.shift();
			namespaces.sort();
		}

		if ( (!elem || jQuery.event.customEvent[ type ]) && !jQuery.event.global[ type ] ) {
			// No jQuery handlers for this event type, and it can't have inline handlers
			return;
		}

		// Caller can pass in an Event, Object, or just an event type string
		event = typeof event === "object" ?
			// jQuery.Event object
			event[ jQuery.expando ] ? event :
			// Object literal
			new jQuery.Event( type, event ) :
			// Just the event type (string)
			new jQuery.Event( type );

		event.type = type;
		event.isTrigger = true;
		event.exclusive = exclusive;
		event.namespace = namespaces.join( "." );
		event.namespace_re = event.namespace? new RegExp("(^|\\.)" + namespaces.join("\\.(?:.*\\.|)") + "(\\.|$)") : null;
		ontype = type.indexOf( ":" ) < 0 ? "on" + type : "";

		// Handle a global trigger
		if ( !elem ) {

			// TODO: Stop taunting the data cache; remove global events and always attach to document
			cache = jQuery.cache;
			for ( i in cache ) {
				if ( cache[ i ].events && cache[ i ].events[ type ] ) {
					jQuery.event.trigger( event, data, cache[ i ].handle.elem, true );
				}
			}
			return;
		}

		// Clean up the event in case it is being reused
		event.result = undefined;
		if ( !event.target ) {
			event.target = elem;
		}

		// Clone any incoming data and prepend the event, creating the handler arg list
		data = data != null ? jQuery.makeArray( data ) : [];
		data.unshift( event );

		// Allow special events to draw outside the lines
		special = jQuery.event.special[ type ] || {};
		if ( special.trigger && special.trigger.apply( elem, data ) === false ) {
			return;
		}

		// Determine event propagation path in advance, per W3C events spec (#9951)
		// Bubble up to document, then to window; watch for a global ownerDocument var (#9724)
		eventPath = [[ elem, special.bindType || type ]];
		if ( !onlyHandlers && !special.noBubble && !jQuery.isWindow( elem ) ) {

			bubbleType = special.delegateType || type;
			cur = rfocusMorph.test( bubbleType + type ) ? elem : elem.parentNode;
			for ( old = elem; cur; cur = cur.parentNode ) {
				eventPath.push([ cur, bubbleType ]);
				old = cur;
			}

			// Only add window if we got to document (e.g., not plain obj or detached DOM)
			if ( old === (elem.ownerDocument || document) ) {
				eventPath.push([ old.defaultView || old.parentWindow || window, bubbleType ]);
			}
		}

		// Fire handlers on the event path
		for ( i = 0; i < eventPath.length && !event.isPropagationStopped(); i++ ) {

			cur = eventPath[i][0];
			event.type = eventPath[i][1];

			handle = ( jQuery._data( cur, "events" ) || {} )[ event.type ] && jQuery._data( cur, "handle" );
			if ( handle ) {
				handle.apply( cur, data );
			}
			// Note that this is a bare JS function and not a jQuery handler
			handle = ontype && cur[ ontype ];
			if ( handle && jQuery.acceptData( cur ) && handle.apply && handle.apply( cur, data ) === false ) {
				event.preventDefault();
			}
		}
		event.type = type;

		// If nobody prevented the default action, do it now
		if ( !onlyHandlers && !event.isDefaultPrevented() ) {

			if ( (!special._default || special._default.apply( elem.ownerDocument, data ) === false) &&
				!(type === "click" && jQuery.nodeName( elem, "a" )) && jQuery.acceptData( elem ) ) {

				// Call a native DOM method on the target with the same name name as the event.
				// Can't use an .isFunction() check here because IE6/7 fails that test.
				// Don't do default actions on window, that's where global variables be (#6170)
				// IE<9 dies on focus/blur to hidden element (#1486)
				if ( ontype && elem[ type ] && ((type !== "focus" && type !== "blur") || event.target.offsetWidth !== 0) && !jQuery.isWindow( elem ) ) {

					// Don't re-trigger an onFOO event when we call its FOO() method
					old = elem[ ontype ];

					if ( old ) {
						elem[ ontype ] = null;
					}

					// Prevent re-triggering of the same event, since we already bubbled it above
					jQuery.event.triggered = type;
					elem[ type ]();
					jQuery.event.triggered = undefined;

					if ( old ) {
						elem[ ontype ] = old;
					}
				}
			}
		}

		return event.result;
	},

	dispatch: function( event ) {

		// Make a writable jQuery.Event from the native event object
		event = jQuery.event.fix( event || window.event );

		var i, j, cur, ret, selMatch, matched, matches, handleObj, sel, related,
			handlers = ( (jQuery._data( this, "events" ) || {} )[ event.type ] || []),
			delegateCount = handlers.delegateCount,
			args = core_slice.call( arguments ),
			run_all = !event.exclusive && !event.namespace,
			special = jQuery.event.special[ event.type ] || {},
			handlerQueue = [];

		// Use the fix-ed jQuery.Event rather than the (read-only) native event
		args[0] = event;
		event.delegateTarget = this;

		// Call the preDispatch hook for the mapped type, and let it bail if desired
		if ( special.preDispatch && special.preDispatch.call( this, event ) === false ) {
			return;
		}

		// Determine handlers that should run if there are delegated events
		// Avoid non-left-click bubbling in Firefox (#3861)
		if ( delegateCount && !(event.button && event.type === "click") ) {

			for ( cur = event.target; cur != this; cur = cur.parentNode || this ) {

				// Don't process clicks (ONLY) on disabled elements (#6911, #8165, #11382, #11764)
				if ( cur.disabled !== true || event.type !== "click" ) {
					selMatch = {};
					matches = [];
					for ( i = 0; i < delegateCount; i++ ) {
						handleObj = handlers[ i ];
						sel = handleObj.selector;

						if ( selMatch[ sel ] === undefined ) {
							selMatch[ sel ] = handleObj.needsContext ?
								jQuery( sel, this ).index( cur ) >= 0 :
								jQuery.find( sel, this, null, [ cur ] ).length;
						}
						if ( selMatch[ sel ] ) {
							matches.push( handleObj );
						}
					}
					if ( matches.length ) {
						handlerQueue.push({ elem: cur, matches: matches });
					}
				}
			}
		}

		// Add the remaining (directly-bound) handlers
		if ( handlers.length > delegateCount ) {
			handlerQueue.push({ elem: this, matches: handlers.slice( delegateCount ) });
		}

		// Run delegates first; they may want to stop propagation beneath us
		for ( i = 0; i < handlerQueue.length && !event.isPropagationStopped(); i++ ) {
			matched = handlerQueue[ i ];
			event.currentTarget = matched.elem;

			for ( j = 0; j < matched.matches.length && !event.isImmediatePropagationStopped(); j++ ) {
				handleObj = matched.matches[ j ];

				// Triggered event must either 1) be non-exclusive and have no namespace, or
				// 2) have namespace(s) a subset or equal to those in the bound event (both can have no namespace).
				if ( run_all || (!event.namespace && !handleObj.namespace) || event.namespace_re && event.namespace_re.test( handleObj.namespace ) ) {

					event.data = handleObj.data;
					event.handleObj = handleObj;

					ret = ( (jQuery.event.special[ handleObj.origType ] || {}).handle || handleObj.handler )
							.apply( matched.elem, args );

					if ( ret !== undefined ) {
						event.result = ret;
						if ( ret === false ) {
							event.preventDefault();
							event.stopPropagation();
						}
					}
				}
			}
		}

		// Call the postDispatch hook for the mapped type
		if ( special.postDispatch ) {
			special.postDispatch.call( this, event );
		}

		return event.result;
	},

	// Includes some event props shared by KeyEvent and MouseEvent
	// *** attrChange attrName relatedNode srcElement  are not normalized, non-W3C, deprecated, will be removed in 1.8 ***
	props: "attrChange attrName relatedNode srcElement altKey bubbles cancelable ctrlKey currentTarget eventPhase metaKey relatedTarget shiftKey target timeStamp view which".split(" "),

	fixHooks: {},

	keyHooks: {
		props: "char charCode key keyCode".split(" "),
		filter: function( event, original ) {

			// Add which for key events
			if ( event.which == null ) {
				event.which = original.charCode != null ? original.charCode : original.keyCode;
			}

			return event;
		}
	},

	mouseHooks: {
		props: "button buttons clientX clientY fromElement offsetX offsetY pageX pageY screenX screenY toElement".split(" "),
		filter: function( event, original ) {
			var eventDoc, doc, body,
				button = original.button,
				fromElement = original.fromElement;

			// Calculate pageX/Y if missing and clientX/Y available
			if ( event.pageX == null && original.clientX != null ) {
				eventDoc = event.target.ownerDocument || document;
				doc = eventDoc.documentElement;
				body = eventDoc.body;

				event.pageX = original.clientX + ( doc && doc.scrollLeft || body && body.scrollLeft || 0 ) - ( doc && doc.clientLeft || body && body.clientLeft || 0 );
				event.pageY = original.clientY + ( doc && doc.scrollTop  || body && body.scrollTop  || 0 ) - ( doc && doc.clientTop  || body && body.clientTop  || 0 );
			}

			// Add relatedTarget, if necessary
			if ( !event.relatedTarget && fromElement ) {
				event.relatedTarget = fromElement === event.target ? original.toElement : fromElement;
			}

			// Add which for click: 1 === left; 2 === middle; 3 === right
			// Note: button is not normalized, so don't use it
			if ( !event.which && button !== undefined ) {
				event.which = ( button & 1 ? 1 : ( button & 2 ? 3 : ( button & 4 ? 2 : 0 ) ) );
			}

			return event;
		}
	},

	fix: function( event ) {
		if ( event[ jQuery.expando ] ) {
			return event;
		}

		// Create a writable copy of the event object and normalize some properties
		var i, prop,
			originalEvent = event,
			fixHook = jQuery.event.fixHooks[ event.type ] || {},
			copy = fixHook.props ? this.props.concat( fixHook.props ) : this.props;

		event = jQuery.Event( originalEvent );

		for ( i = copy.length; i; ) {
			prop = copy[ --i ];
			event[ prop ] = originalEvent[ prop ];
		}

		// Fix target property, if necessary (#1925, IE 6/7/8 & Safari2)
		if ( !event.target ) {
			event.target = originalEvent.srcElement || document;
		}

		// Target should not be a text node (#504, Safari)
		if ( event.target.nodeType === 3 ) {
			event.target = event.target.parentNode;
		}

		// For mouse/key events, metaKey==false if it's undefined (#3368, #11328; IE6/7/8)
		event.metaKey = !!event.metaKey;

		return fixHook.filter? fixHook.filter( event, originalEvent ) : event;
	},

	special: {
		load: {
			// Prevent triggered image.load events from bubbling to window.load
			noBubble: true
		},

		focus: {
			delegateType: "focusin"
		},
		blur: {
			delegateType: "focusout"
		},

		beforeunload: {
			setup: function( data, namespaces, eventHandle ) {
				// We only want to do this special case on windows
				if ( jQuery.isWindow( this ) ) {
					this.onbeforeunload = eventHandle;
				}
			},

			teardown: function( namespaces, eventHandle ) {
				if ( this.onbeforeunload === eventHandle ) {
					this.onbeforeunload = null;
				}
			}
		}
	},

	simulate: function( type, elem, event, bubble ) {
		// Piggyback on a donor event to simulate a different one.
		// Fake originalEvent to avoid donor's stopPropagation, but if the
		// simulated event prevents default then we do the same on the donor.
		var e = jQuery.extend(
			new jQuery.Event(),
			event,
			{ type: type,
				isSimulated: true,
				originalEvent: {}
			}
		);
		if ( bubble ) {
			jQuery.event.trigger( e, null, elem );
		} else {
			jQuery.event.dispatch.call( elem, e );
		}
		if ( e.isDefaultPrevented() ) {
			event.preventDefault();
		}
	}
};

// Some plugins are using, but it's undocumented/deprecated and will be removed.
// The 1.7 special event interface should provide all the hooks needed now.
jQuery.event.handle = jQuery.event.dispatch;

jQuery.removeEvent = document.removeEventListener ?
	function( elem, type, handle ) {
		if ( elem.removeEventListener ) {
			elem.removeEventListener( type, handle, false );
		}
	} :
	function( elem, type, handle ) {
		var name = "on" + type;

		if ( elem.detachEvent ) {

			// #8545, #7054, preventing memory leaks for custom events in IE6-8
			// detachEvent needed property on element, by name of that event, to properly expose it to GC
			if ( typeof elem[ name ] === "undefined" ) {
				elem[ name ] = null;
			}

			elem.detachEvent( name, handle );
		}
	};

jQuery.Event = function( src, props ) {
	// Allow instantiation without the 'new' keyword
	if ( !(this instanceof jQuery.Event) ) {
		return new jQuery.Event( src, props );
	}

	// Event object
	if ( src && src.type ) {
		this.originalEvent = src;
		this.type = src.type;

		// Events bubbling up the document may have been marked as prevented
		// by a handler lower down the tree; reflect the correct value.
		this.isDefaultPrevented = ( src.defaultPrevented || src.returnValue === false ||
			src.getPreventDefault && src.getPreventDefault() ) ? returnTrue : returnFalse;

	// Event type
	} else {
		this.type = src;
	}

	// Put explicitly provided properties onto the event object
	if ( props ) {
		jQuery.extend( this, props );
	}

	// Create a timestamp if incoming event doesn't have one
	this.timeStamp = src && src.timeStamp || jQuery.now();

	// Mark it as fixed
	this[ jQuery.expando ] = true;
};

function returnFalse() {
	return false;
}
function returnTrue() {
	return true;
}

// jQuery.Event is based on DOM3 Events as specified by the ECMAScript Language Binding
// http://www.w3.org/TR/2003/WD-DOM-Level-3-Events-20030331/ecma-script-binding.html
jQuery.Event.prototype = {
	preventDefault: function() {
		this.isDefaultPrevented = returnTrue;

		var e = this.originalEvent;
		if ( !e ) {
			return;
		}

		// if preventDefault exists run it on the original event
		if ( e.preventDefault ) {
			e.preventDefault();

		// otherwise set the returnValue property of the original event to false (IE)
		} else {
			e.returnValue = false;
		}
	},
	stopPropagation: function() {
		this.isPropagationStopped = returnTrue;

		var e = this.originalEvent;
		if ( !e ) {
			return;
		}
		// if stopPropagation exists run it on the original event
		if ( e.stopPropagation ) {
			e.stopPropagation();
		}
		// otherwise set the cancelBubble property of the original event to true (IE)
		e.cancelBubble = true;
	},
	stopImmediatePropagation: function() {
		this.isImmediatePropagationStopped = returnTrue;
		this.stopPropagation();
	},
	isDefaultPrevented: returnFalse,
	isPropagationStopped: returnFalse,
	isImmediatePropagationStopped: returnFalse
};

// Create mouseenter/leave events using mouseover/out and event-time checks
jQuery.each({
	mouseenter: "mouseover",
	mouseleave: "mouseout"
}, function( orig, fix ) {
	jQuery.event.special[ orig ] = {
		delegateType: fix,
		bindType: fix,

		handle: function( event ) {
			var ret,
				target = this,
				related = event.relatedTarget,
				handleObj = event.handleObj,
				selector = handleObj.selector;

			// For mousenter/leave call the handler if related is outside the target.
			// NB: No relatedTarget if the mouse left/entered the browser window
			if ( !related || (related !== target && !jQuery.contains( target, related )) ) {
				event.type = handleObj.origType;
				ret = handleObj.handler.apply( this, arguments );
				event.type = fix;
			}
			return ret;
		}
	};
});

// IE submit delegation
if ( !jQuery.support.submitBubbles ) {

	jQuery.event.special.submit = {
		setup: function() {
			// Only need this for delegated form submit events
			if ( jQuery.nodeName( this, "form" ) ) {
				return false;
			}

			// Lazy-add a submit handler when a descendant form may potentially be submitted
			jQuery.event.add( this, "click._submit keypress._submit", function( e ) {
				// Node name check avoids a VML-related crash in IE (#9807)
				var elem = e.target,
					form = jQuery.nodeName( elem, "input" ) || jQuery.nodeName( elem, "button" ) ? elem.form : undefined;
				if ( form && !jQuery._data( form, "_submit_attached" ) ) {
					jQuery.event.add( form, "submit._submit", function( event ) {
						event._submit_bubble = true;
					});
					jQuery._data( form, "_submit_attached", true );
				}
			});
			// return undefined since we don't need an event listener
		},

		postDispatch: function( event ) {
			// If form was submitted by the user, bubble the event up the tree
			if ( event._submit_bubble ) {
				delete event._submit_bubble;
				if ( this.parentNode && !event.isTrigger ) {
					jQuery.event.simulate( "submit", this.parentNode, event, true );
				}
			}
		},

		teardown: function() {
			// Only need this for delegated form submit events
			if ( jQuery.nodeName( this, "form" ) ) {
				return false;
			}

			// Remove delegated handlers; cleanData eventually reaps submit handlers attached above
			jQuery.event.remove( this, "._submit" );
		}
	};
}

// IE change delegation and checkbox/radio fix
if ( !jQuery.support.changeBubbles ) {

	jQuery.event.special.change = {

		setup: function() {

			if ( rformElems.test( this.nodeName ) ) {
				// IE doesn't fire change on a check/radio until blur; trigger it on click
				// after a propertychange. Eat the blur-change in special.change.handle.
				// This still fires onchange a second time for check/radio after blur.
				if ( this.type === "checkbox" || this.type === "radio" ) {
					jQuery.event.add( this, "propertychange._change", function( event ) {
						if ( event.originalEvent.propertyName === "checked" ) {
							this._just_changed = true;
						}
					});
					jQuery.event.add( this, "click._change", function( event ) {
						if ( this._just_changed && !event.isTrigger ) {
							this._just_changed = false;
						}
						// Allow triggered, simulated change events (#11500)
						jQuery.event.simulate( "change", this, event, true );
					});
				}
				return false;
			}
			// Delegated event; lazy-add a change handler on descendant inputs
			jQuery.event.add( this, "beforeactivate._change", function( e ) {
				var elem = e.target;

				if ( rformElems.test( elem.nodeName ) && !jQuery._data( elem, "_change_attached" ) ) {
					jQuery.event.add( elem, "change._change", function( event ) {
						if ( this.parentNode && !event.isSimulated && !event.isTrigger ) {
							jQuery.event.simulate( "change", this.parentNode, event, true );
						}
					});
					jQuery._data( elem, "_change_attached", true );
				}
			});
		},

		handle: function( event ) {
			var elem = event.target;

			// Swallow native change events from checkbox/radio, we already triggered them above
			if ( this !== elem || event.isSimulated || event.isTrigger || (elem.type !== "radio" && elem.type !== "checkbox") ) {
				return event.handleObj.handler.apply( this, arguments );
			}
		},

		teardown: function() {
			jQuery.event.remove( this, "._change" );

			return !rformElems.test( this.nodeName );
		}
	};
}

// Create "bubbling" focus and blur events
if ( !jQuery.support.focusinBubbles ) {
	jQuery.each({ focus: "focusin", blur: "focusout" }, function( orig, fix ) {

		// Attach a single capturing handler while someone wants focusin/focusout
		var attaches = 0,
			handler = function( event ) {
				jQuery.event.simulate( fix, event.target, jQuery.event.fix( event ), true );
			};

		jQuery.event.special[ fix ] = {
			setup: function() {
				if ( attaches++ === 0 ) {
					document.addEventListener( orig, handler, true );
				}
			},
			teardown: function() {
				if ( --attaches === 0 ) {
					document.removeEventListener( orig, handler, true );
				}
			}
		};
	});
}

jQuery.fn.extend({

	on: function( types, selector, data, fn, /*INTERNAL*/ one ) {
		var origFn, type;

		// Types can be a map of types/handlers
		if ( typeof types === "object" ) {
			// ( types-Object, selector, data )
			if ( typeof selector !== "string" ) { // && selector != null
				// ( types-Object, data )
				data = data || selector;
				selector = undefined;
			}
			for ( type in types ) {
				this.on( type, selector, data, types[ type ], one );
			}
			return this;
		}

		if ( data == null && fn == null ) {
			// ( types, fn )
			fn = selector;
			data = selector = undefined;
		} else if ( fn == null ) {
			if ( typeof selector === "string" ) {
				// ( types, selector, fn )
				fn = data;
				data = undefined;
			} else {
				// ( types, data, fn )
				fn = data;
				data = selector;
				selector = undefined;
			}
		}
		if ( fn === false ) {
			fn = returnFalse;
		} else if ( !fn ) {
			return this;
		}

		if ( one === 1 ) {
			origFn = fn;
			fn = function( event ) {
				// Can use an empty set, since event contains the info
				jQuery().off( event );
				return origFn.apply( this, arguments );
			};
			// Use same guid so caller can remove using origFn
			fn.guid = origFn.guid || ( origFn.guid = jQuery.guid++ );
		}
		return this.each( function() {
			jQuery.event.add( this, types, fn, data, selector );
		});
	},
	one: function( types, selector, data, fn ) {
		return this.on( types, selector, data, fn, 1 );
	},
	off: function( types, selector, fn ) {
		var handleObj, type;
		if ( types && types.preventDefault && types.handleObj ) {
			// ( event )  dispatched jQuery.Event
			handleObj = types.handleObj;
			jQuery( types.delegateTarget ).off(
				handleObj.namespace ? handleObj.origType + "." + handleObj.namespace : handleObj.origType,
				handleObj.selector,
				handleObj.handler
			);
			return this;
		}
		if ( typeof types === "object" ) {
			// ( types-object [, selector] )
			for ( type in types ) {
				this.off( type, selector, types[ type ] );
			}
			return this;
		}
		if ( selector === false || typeof selector === "function" ) {
			// ( types [, fn] )
			fn = selector;
			selector = undefined;
		}
		if ( fn === false ) {
			fn = returnFalse;
		}
		return this.each(function() {
			jQuery.event.remove( this, types, fn, selector );
		});
	},

	bind: function( types, data, fn ) {
		return this.on( types, null, data, fn );
	},
	unbind: function( types, fn ) {
		return this.off( types, null, fn );
	},

	live: function( types, data, fn ) {
		jQuery( this.context ).on( types, this.selector, data, fn );
		return this;
	},
	die: function( types, fn ) {
		jQuery( this.context ).off( types, this.selector || "**", fn );
		return this;
	},

	delegate: function( selector, types, data, fn ) {
		return this.on( types, selector, data, fn );
	},
	undelegate: function( selector, types, fn ) {
		// ( namespace ) or ( selector, types [, fn] )
		return arguments.length === 1 ? this.off( selector, "**" ) : this.off( types, selector || "**", fn );
	},

	trigger: function( type, data ) {
		return this.each(function() {
			jQuery.event.trigger( type, data, this );
		});
	},
	triggerHandler: function( type, data ) {
		if ( this[0] ) {
			return jQuery.event.trigger( type, data, this[0], true );
		}
	},

	toggle: function( fn ) {
		// Save reference to arguments for access in closure
		var args = arguments,
			guid = fn.guid || jQuery.guid++,
			i = 0,
			toggler = function( event ) {
				// Figure out which function to execute
				var lastToggle = ( jQuery._data( this, "lastToggle" + fn.guid ) || 0 ) % i;
				jQuery._data( this, "lastToggle" + fn.guid, lastToggle + 1 );

				// Make sure that clicks stop
				event.preventDefault();

				// and execute the function
				return args[ lastToggle ].apply( this, arguments ) || false;
			};

		// link all the functions, so any of them can unbind this click handler
		toggler.guid = guid;
		while ( i < args.length ) {
			args[ i++ ].guid = guid;
		}

		return this.click( toggler );
	},

	hover: function( fnOver, fnOut ) {
		return this.mouseenter( fnOver ).mouseleave( fnOut || fnOver );
	}
});

jQuery.each( ("blur focus focusin focusout load resize scroll unload click dblclick " +
	"mousedown mouseup mousemove mouseover mouseout mouseenter mouseleave " +
	"change select submit keydown keypress keyup error contextmenu").split(" "), function( i, name ) {

	// Handle event binding
	jQuery.fn[ name ] = function( data, fn ) {
		if ( fn == null ) {
			fn = data;
			data = null;
		}

		return arguments.length > 0 ?
			this.on( name, null, data, fn ) :
			this.trigger( name );
	};

	if ( rkeyEvent.test( name ) ) {
		jQuery.event.fixHooks[ name ] = jQuery.event.keyHooks;
	}

	if ( rmouseEvent.test( name ) ) {
		jQuery.event.fixHooks[ name ] = jQuery.event.mouseHooks;
	}
});
/*!
 * Sizzle CSS Selector Engine
 * Copyright 2012 jQuery Foundation and other contributors
 * Released under the MIT license
 * http://sizzlejs.com/
 */
(function( window, undefined ) {

var cachedruns,
	assertGetIdNotName,
	Expr,
	getText,
	isXML,
	contains,
	compile,
	sortOrder,
	hasDuplicate,
	outermostContext,

	baseHasDuplicate = true,
	strundefined = "undefined",

	expando = ( "sizcache" + Math.random() ).replace( ".", "" ),

	Token = String,
	document = window.document,
	docElem = document.documentElement,
	dirruns = 0,
	done = 0,
	pop = [].pop,
	push = [].push,
	slice = [].slice,
	// Use a stripped-down indexOf if a native one is unavailable
	indexOf = [].indexOf || function( elem ) {
		var i = 0,
			len = this.length;
		for ( ; i < len; i++ ) {
			if ( this[i] === elem ) {
				return i;
			}
		}
		return -1;
	},

	// Augment a function for special use by Sizzle
	markFunction = function( fn, value ) {
		fn[ expando ] = value == null || value;
		return fn;
	},

	createCache = function() {
		var cache = {},
			keys = [];

		return markFunction(function( key, value ) {
			// Only keep the most recent entries
			if ( keys.push( key ) > Expr.cacheLength ) {
				delete cache[ keys.shift() ];
			}

			// Retrieve with (key + " ") to avoid collision with native Object.prototype properties (see Issue #157)
			return (cache[ key + " " ] = value);
		}, cache );
	},

	classCache = createCache(),
	tokenCache = createCache(),
	compilerCache = createCache(),

	// Regex

	// Whitespace characters http://www.w3.org/TR/css3-selectors/#whitespace
	whitespace = "[\\x20\\t\\r\\n\\f]",
	// http://www.w3.org/TR/css3-syntax/#characters
	characterEncoding = "(?:\\\\.|[-\\w]|[^\\x00-\\xa0])+",

	// Loosely modeled on CSS identifier characters
	// An unquoted value should be a CSS identifier (http://www.w3.org/TR/css3-selectors/#attribute-selectors)
	// Proper syntax: http://www.w3.org/TR/CSS21/syndata.html#value-def-identifier
	identifier = characterEncoding.replace( "w", "w#" ),

	// Acceptable operators http://www.w3.org/TR/selectors/#attribute-selectors
	operators = "([*^$|!~]?=)",
	attributes = "\\[" + whitespace + "*(" + characterEncoding + ")" + whitespace +
		"*(?:" + operators + whitespace + "*(?:(['\"])((?:\\\\.|[^\\\\])*?)\\3|(" + identifier + ")|)|)" + whitespace + "*\\]",

	// Prefer arguments not in parens/brackets,
	//   then attribute selectors and non-pseudos (denoted by :),
	//   then anything else
	// These preferences are here to reduce the number of selectors
	//   needing tokenize in the PSEUDO preFilter
	pseudos = ":(" + characterEncoding + ")(?:\\((?:(['\"])((?:\\\\.|[^\\\\])*?)\\2|([^()[\\]]*|(?:(?:" + attributes + ")|[^:]|\\\\.)*|.*))\\)|)",

	// For matchExpr.POS and matchExpr.needsContext
	pos = ":(even|odd|eq|gt|lt|nth|first|last)(?:\\(" + whitespace +
		"*((?:-\\d)?\\d*)" + whitespace + "*\\)|)(?=[^-]|$)",

	// Leading and non-escaped trailing whitespace, capturing some non-whitespace characters preceding the latter
	rtrim = new RegExp( "^" + whitespace + "+|((?:^|[^\\\\])(?:\\\\.)*)" + whitespace + "+$", "g" ),

	rcomma = new RegExp( "^" + whitespace + "*," + whitespace + "*" ),
	rcombinators = new RegExp( "^" + whitespace + "*([\\x20\\t\\r\\n\\f>+~])" + whitespace + "*" ),
	rpseudo = new RegExp( pseudos ),

	// Easily-parseable/retrievable ID or TAG or CLASS selectors
	rquickExpr = /^(?:#([\w\-]+)|(\w+)|\.([\w\-]+))$/,

	rnot = /^:not/,
	rsibling = /[\x20\t\r\n\f]*[+~]/,
	rendsWithNot = /:not\($/,

	rheader = /h\d/i,
	rinputs = /input|select|textarea|button/i,

	rbackslash = /\\(?!\\)/g,

	matchExpr = {
		"ID": new RegExp( "^#(" + characterEncoding + ")" ),
		"CLASS": new RegExp( "^\\.(" + characterEncoding + ")" ),
		"NAME": new RegExp( "^\\[name=['\"]?(" + characterEncoding + ")['\"]?\\]" ),
		"TAG": new RegExp( "^(" + characterEncoding.replace( "w", "w*" ) + ")" ),
		"ATTR": new RegExp( "^" + attributes ),
		"PSEUDO": new RegExp( "^" + pseudos ),
		"POS": new RegExp( pos, "i" ),
		"CHILD": new RegExp( "^:(only|nth|first|last)-child(?:\\(" + whitespace +
			"*(even|odd|(([+-]|)(\\d*)n|)" + whitespace + "*(?:([+-]|)" + whitespace +
			"*(\\d+)|))" + whitespace + "*\\)|)", "i" ),
		// For use in libraries implementing .is()
		"needsContext": new RegExp( "^" + whitespace + "*[>+~]|" + pos, "i" )
	},

	// Support

	// Used for testing something on an element
	assert = function( fn ) {
		var div = document.createElement("div");

		try {
			return fn( div );
		} catch (e) {
			return false;
		} finally {
			// release memory in IE
			div = null;
		}
	},

	// Check if getElementsByTagName("*") returns only elements
	assertTagNameNoComments = assert(function( div ) {
		div.appendChild( document.createComment("") );
		return !div.getElementsByTagName("*").length;
	}),

	// Check if getAttribute returns normalized href attributes
	assertHrefNotNormalized = assert(function( div ) {
		div.innerHTML = "<a href='#'></a>";
		return div.firstChild && typeof div.firstChild.getAttribute !== strundefined &&
			div.firstChild.getAttribute("href") === "#";
	}),

	// Check if attributes should be retrieved by attribute nodes
	assertAttributes = assert(function( div ) {
		div.innerHTML = "<select></select>";
		var type = typeof div.lastChild.getAttribute("multiple");
		// IE8 returns a string for some attributes even when not present
		return type !== "boolean" && type !== "string";
	}),

	// Check if getElementsByClassName can be trusted
	assertUsableClassName = assert(function( div ) {
		// Opera can't find a second classname (in 9.6)
		div.innerHTML = "<div class='hidden e'></div><div class='hidden'></div>";
		if ( !div.getElementsByClassName || !div.getElementsByClassName("e").length ) {
			return false;
		}

		// Safari 3.2 caches class attributes and doesn't catch changes
		div.lastChild.className = "e";
		return div.getElementsByClassName("e").length === 2;
	}),

	// Check if getElementById returns elements by name
	// Check if getElementsByName privileges form controls or returns elements by ID
	assertUsableName = assert(function( div ) {
		// Inject content
		div.id = expando + 0;
		div.innerHTML = "<a name='" + expando + "'></a><div name='" + expando + "'></div>";
		docElem.insertBefore( div, docElem.firstChild );

		// Test
		var pass = document.getElementsByName &&
			// buggy browsers will return fewer than the correct 2
			document.getElementsByName( expando ).length === 2 +
			// buggy browsers will return more than the correct 0
			document.getElementsByName( expando + 0 ).length;
		assertGetIdNotName = !document.getElementById( expando );

		// Cleanup
		docElem.removeChild( div );

		return pass;
	});

// If slice is not available, provide a backup
try {
	slice.call( docElem.childNodes, 0 )[0].nodeType;
} catch ( e ) {
	slice = function( i ) {
		var elem,
			results = [];
		for ( ; (elem = this[i]); i++ ) {
			results.push( elem );
		}
		return results;
	};
}

function Sizzle( selector, context, results, seed ) {
	results = results || [];
	context = context || document;
	var match, elem, xml, m,
		nodeType = context.nodeType;

	if ( !selector || typeof selector !== "string" ) {
		return results;
	}

	if ( nodeType !== 1 && nodeType !== 9 ) {
		return [];
	}

	xml = isXML( context );

	if ( !xml && !seed ) {
		if ( (match = rquickExpr.exec( selector )) ) {
			// Speed-up: Sizzle("#ID")
			if ( (m = match[1]) ) {
				if ( nodeType === 9 ) {
					elem = context.getElementById( m );
					// Check parentNode to catch when Blackberry 4.6 returns
					// nodes that are no longer in the document #6963
					if ( elem && elem.parentNode ) {
						// Handle the case where IE, Opera, and Webkit return items
						// by name instead of ID
						if ( elem.id === m ) {
							results.push( elem );
							return results;
						}
					} else {
						return results;
					}
				} else {
					// Context is not a document
					if ( context.ownerDocument && (elem = context.ownerDocument.getElementById( m )) &&
						contains( context, elem ) && elem.id === m ) {
						results.push( elem );
						return results;
					}
				}

			// Speed-up: Sizzle("TAG")
			} else if ( match[2] ) {
				push.apply( results, slice.call(context.getElementsByTagName( selector ), 0) );
				return results;

			// Speed-up: Sizzle(".CLASS")
			} else if ( (m = match[3]) && assertUsableClassName && context.getElementsByClassName ) {
				push.apply( results, slice.call(context.getElementsByClassName( m ), 0) );
				return results;
			}
		}
	}

	// All others
	return select( selector.replace( rtrim, "$1" ), context, results, seed, xml );
}

Sizzle.matches = function( expr, elements ) {
	return Sizzle( expr, null, null, elements );
};

Sizzle.matchesSelector = function( elem, expr ) {
	return Sizzle( expr, null, null, [ elem ] ).length > 0;
};

// Returns a function to use in pseudos for input types
function createInputPseudo( type ) {
	return function( elem ) {
		var name = elem.nodeName.toLowerCase();
		return name === "input" && elem.type === type;
	};
}

// Returns a function to use in pseudos for buttons
function createButtonPseudo( type ) {
	return function( elem ) {
		var name = elem.nodeName.toLowerCase();
		return (name === "input" || name === "button") && elem.type === type;
	};
}

// Returns a function to use in pseudos for positionals
function createPositionalPseudo( fn ) {
	return markFunction(function( argument ) {
		argument = +argument;
		return markFunction(function( seed, matches ) {
			var j,
				matchIndexes = fn( [], seed.length, argument ),
				i = matchIndexes.length;

			// Match elements found at the specified indexes
			while ( i-- ) {
				if ( seed[ (j = matchIndexes[i]) ] ) {
					seed[j] = !(matches[j] = seed[j]);
				}
			}
		});
	});
}

/**
 * Utility function for retrieving the text value of an array of DOM nodes
 * @param {Array|Element} elem
 */
getText = Sizzle.getText = function( elem ) {
	var node,
		ret = "",
		i = 0,
		nodeType = elem.nodeType;

	if ( nodeType ) {
		if ( nodeType === 1 || nodeType === 9 || nodeType === 11 ) {
			// Use textContent for elements
			// innerText usage removed for consistency of new lines (see #11153)
			if ( typeof elem.textContent === "string" ) {
				return elem.textContent;
			} else {
				// Traverse its children
				for ( elem = elem.firstChild; elem; elem = elem.nextSibling ) {
					ret += getText( elem );
				}
			}
		} else if ( nodeType === 3 || nodeType === 4 ) {
			return elem.nodeValue;
		}
		// Do not include comment or processing instruction nodes
	} else {

		// If no nodeType, this is expected to be an array
		for ( ; (node = elem[i]); i++ ) {
			// Do not traverse comment nodes
			ret += getText( node );
		}
	}
	return ret;
};

isXML = Sizzle.isXML = function( elem ) {
	// documentElement is verified for cases where it doesn't yet exist
	// (such as loading iframes in IE - #4833)
	var documentElement = elem && (elem.ownerDocument || elem).documentElement;
	return documentElement ? documentElement.nodeName !== "HTML" : false;
};

// Element contains another
contains = Sizzle.contains = docElem.contains ?
	function( a, b ) {
		var adown = a.nodeType === 9 ? a.documentElement : a,
			bup = b && b.parentNode;
		return a === bup || !!( bup && bup.nodeType === 1 && adown.contains && adown.contains(bup) );
	} :
	docElem.compareDocumentPosition ?
	function( a, b ) {
		return b && !!( a.compareDocumentPosition( b ) & 16 );
	} :
	function( a, b ) {
		while ( (b = b.parentNode) ) {
			if ( b === a ) {
				return true;
			}
		}
		return false;
	};

Sizzle.attr = function( elem, name ) {
	var val,
		xml = isXML( elem );

	if ( !xml ) {
		name = name.toLowerCase();
	}
	if ( (val = Expr.attrHandle[ name ]) ) {
		return val( elem );
	}
	if ( xml || assertAttributes ) {
		return elem.getAttribute( name );
	}
	val = elem.getAttributeNode( name );
	return val ?
		typeof elem[ name ] === "boolean" ?
			elem[ name ] ? name : null :
			val.specified ? val.value : null :
		null;
};

Expr = Sizzle.selectors = {

	// Can be adjusted by the user
	cacheLength: 50,

	createPseudo: markFunction,

	match: matchExpr,

	// IE6/7 return a modified href
	attrHandle: assertHrefNotNormalized ?
		{} :
		{
			"href": function( elem ) {
				return elem.getAttribute( "href", 2 );
			},
			"type": function( elem ) {
				return elem.getAttribute("type");
			}
		},

	find: {
		"ID": assertGetIdNotName ?
			function( id, context, xml ) {
				if ( typeof context.getElementById !== strundefined && !xml ) {
					var m = context.getElementById( id );
					// Check parentNode to catch when Blackberry 4.6 returns
					// nodes that are no longer in the document #6963
					return m && m.parentNode ? [m] : [];
				}
			} :
			function( id, context, xml ) {
				if ( typeof context.getElementById !== strundefined && !xml ) {
					var m = context.getElementById( id );

					return m ?
						m.id === id || typeof m.getAttributeNode !== strundefined && m.getAttributeNode("id").value === id ?
							[m] :
							undefined :
						[];
				}
			},

		"TAG": assertTagNameNoComments ?
			function( tag, context ) {
				if ( typeof context.getElementsByTagName !== strundefined ) {
					return context.getElementsByTagName( tag );
				}
			} :
			function( tag, context ) {
				var results = context.getElementsByTagName( tag );

				// Filter out possible comments
				if ( tag === "*" ) {
					var elem,
						tmp = [],
						i = 0;

					for ( ; (elem = results[i]); i++ ) {
						if ( elem.nodeType === 1 ) {
							tmp.push( elem );
						}
					}

					return tmp;
				}
				return results;
			},

		"NAME": assertUsableName && function( tag, context ) {
			if ( typeof context.getElementsByName !== strundefined ) {
				return context.getElementsByName( name );
			}
		},

		"CLASS": assertUsableClassName && function( className, context, xml ) {
			if ( typeof context.getElementsByClassName !== strundefined && !xml ) {
				return context.getElementsByClassName( className );
			}
		}
	},

	relative: {
		">": { dir: "parentNode", first: true },
		" ": { dir: "parentNode" },
		"+": { dir: "previousSibling", first: true },
		"~": { dir: "previousSibling" }
	},

	preFilter: {
		"ATTR": function( match ) {
			match[1] = match[1].replace( rbackslash, "" );

			// Move the given value to match[3] whether quoted or unquoted
			match[3] = ( match[4] || match[5] || "" ).replace( rbackslash, "" );

			if ( match[2] === "~=" ) {
				match[3] = " " + match[3] + " ";
			}

			return match.slice( 0, 4 );
		},

		"CHILD": function( match ) {
			/* matches from matchExpr["CHILD"]
				1 type (only|nth|...)
				2 argument (even|odd|\d*|\d*n([+-]\d+)?|...)
				3 xn-component of xn+y argument ([+-]?\d*n|)
				4 sign of xn-component
				5 x of xn-component
				6 sign of y-component
				7 y of y-component
			*/
			match[1] = match[1].toLowerCase();

			if ( match[1] === "nth" ) {
				// nth-child requires argument
				if ( !match[2] ) {
					Sizzle.error( match[0] );
				}

				// numeric x and y parameters for Expr.filter.CHILD
				// remember that false/true cast respectively to 0/1
				match[3] = +( match[3] ? match[4] + (match[5] || 1) : 2 * ( match[2] === "even" || match[2] === "odd" ) );
				match[4] = +( ( match[6] + match[7] ) || match[2] === "odd" );

			// other types prohibit arguments
			} else if ( match[2] ) {
				Sizzle.error( match[0] );
			}

			return match;
		},

		"PSEUDO": function( match ) {
			var unquoted, excess;
			if ( matchExpr["CHILD"].test( match[0] ) ) {
				return null;
			}

			if ( match[3] ) {
				match[2] = match[3];
			} else if ( (unquoted = match[4]) ) {
				// Only check arguments that contain a pseudo
				if ( rpseudo.test(unquoted) &&
					// Get excess from tokenize (recursively)
					(excess = tokenize( unquoted, true )) &&
					// advance to the next closing parenthesis
					(excess = unquoted.indexOf( ")", unquoted.length - excess ) - unquoted.length) ) {

					// excess is a negative index
					unquoted = unquoted.slice( 0, excess );
					match[0] = match[0].slice( 0, excess );
				}
				match[2] = unquoted;
			}

			// Return only captures needed by the pseudo filter method (type and argument)
			return match.slice( 0, 3 );
		}
	},

	filter: {
		"ID": assertGetIdNotName ?
			function( id ) {
				id = id.replace( rbackslash, "" );
				return function( elem ) {
					return elem.getAttribute("id") === id;
				};
			} :
			function( id ) {
				id = id.replace( rbackslash, "" );
				return function( elem ) {
					var node = typeof elem.getAttributeNode !== strundefined && elem.getAttributeNode("id");
					return node && node.value === id;
				};
			},

		"TAG": function( nodeName ) {
			if ( nodeName === "*" ) {
				return function() { return true; };
			}
			nodeName = nodeName.replace( rbackslash, "" ).toLowerCase();

			return function( elem ) {
				return elem.nodeName && elem.nodeName.toLowerCase() === nodeName;
			};
		},

		"CLASS": function( className ) {
			var pattern = classCache[ expando ][ className + " " ];

			return pattern ||
				(pattern = new RegExp( "(^|" + whitespace + ")" + className + "(" + whitespace + "|$)" )) &&
				classCache( className, function( elem ) {
					return pattern.test( elem.className || (typeof elem.getAttribute !== strundefined && elem.getAttribute("class")) || "" );
				});
		},

		"ATTR": function( name, operator, check ) {
			return function( elem, context ) {
				var result = Sizzle.attr( elem, name );

				if ( result == null ) {
					return operator === "!=";
				}
				if ( !operator ) {
					return true;
				}

				result += "";

				return operator === "=" ? result === check :
					operator === "!=" ? result !== check :
					operator === "^=" ? check && result.indexOf( check ) === 0 :
					operator === "*=" ? check && result.indexOf( check ) > -1 :
					operator === "$=" ? check && result.substr( result.length - check.length ) === check :
					operator === "~=" ? ( " " + result + " " ).indexOf( check ) > -1 :
					operator === "|=" ? result === check || result.substr( 0, check.length + 1 ) === check + "-" :
					false;
			};
		},

		"CHILD": function( type, argument, first, last ) {

			if ( type === "nth" ) {
				return function( elem ) {
					var node, diff,
						parent = elem.parentNode;

					if ( first === 1 && last === 0 ) {
						return true;
					}

					if ( parent ) {
						diff = 0;
						for ( node = parent.firstChild; node; node = node.nextSibling ) {
							if ( node.nodeType === 1 ) {
								diff++;
								if ( elem === node ) {
									break;
								}
							}
						}
					}

					// Incorporate the offset (or cast to NaN), then check against cycle size
					diff -= last;
					return diff === first || ( diff % first === 0 && diff / first >= 0 );
				};
			}

			return function( elem ) {
				var node = elem;

				switch ( type ) {
					case "only":
					case "first":
						while ( (node = node.previousSibling) ) {
							if ( node.nodeType === 1 ) {
								return false;
							}
						}

						if ( type === "first" ) {
							return true;
						}

						node = elem;

						/* falls through */
					case "last":
						while ( (node = node.nextSibling) ) {
							if ( node.nodeType === 1 ) {
								return false;
							}
						}

						return true;
				}
			};
		},

		"PSEUDO": function( pseudo, argument ) {
			// pseudo-class names are case-insensitive
			// http://www.w3.org/TR/selectors/#pseudo-classes
			// Prioritize by case sensitivity in case custom pseudos are added with uppercase letters
			// Remember that setFilters inherits from pseudos
			var args,
				fn = Expr.pseudos[ pseudo ] || Expr.setFilters[ pseudo.toLowerCase() ] ||
					Sizzle.error( "unsupported pseudo: " + pseudo );

			// The user may use createPseudo to indicate that
			// arguments are needed to create the filter function
			// just as Sizzle does
			if ( fn[ expando ] ) {
				return fn( argument );
			}

			// But maintain support for old signatures
			if ( fn.length > 1 ) {
				args = [ pseudo, pseudo, "", argument ];
				return Expr.setFilters.hasOwnProperty( pseudo.toLowerCase() ) ?
					markFunction(function( seed, matches ) {
						var idx,
							matched = fn( seed, argument ),
							i = matched.length;
						while ( i-- ) {
							idx = indexOf.call( seed, matched[i] );
							seed[ idx ] = !( matches[ idx ] = matched[i] );
						}
					}) :
					function( elem ) {
						return fn( elem, 0, args );
					};
			}

			return fn;
		}
	},

	pseudos: {
		"not": markFunction(function( selector ) {
			// Trim the selector passed to compile
			// to avoid treating leading and trailing
			// spaces as combinators
			var input = [],
				results = [],
				matcher = compile( selector.replace( rtrim, "$1" ) );

			return matcher[ expando ] ?
				markFunction(function( seed, matches, context, xml ) {
					var elem,
						unmatched = matcher( seed, null, xml, [] ),
						i = seed.length;

					// Match elements unmatched by `matcher`
					while ( i-- ) {
						if ( (elem = unmatched[i]) ) {
							seed[i] = !(matches[i] = elem);
						}
					}
				}) :
				function( elem, context, xml ) {
					input[0] = elem;
					matcher( input, null, xml, results );
					return !results.pop();
				};
		}),

		"has": markFunction(function( selector ) {
			return function( elem ) {
				return Sizzle( selector, elem ).length > 0;
			};
		}),

		"contains": markFunction(function( text ) {
			return function( elem ) {
				return ( elem.textContent || elem.innerText || getText( elem ) ).indexOf( text ) > -1;
			};
		}),

		"enabled": function( elem ) {
			return elem.disabled === false;
		},

		"disabled": function( elem ) {
			return elem.disabled === true;
		},

		"checked": function( elem ) {
			// In CSS3, :checked should return both checked and selected elements
			// http://www.w3.org/TR/2011/REC-css3-selectors-20110929/#checked
			var nodeName = elem.nodeName.toLowerCase();
			return (nodeName === "input" && !!elem.checked) || (nodeName === "option" && !!elem.selected);
		},

		"selected": function( elem ) {
			// Accessing this property makes selected-by-default
			// options in Safari work properly
			if ( elem.parentNode ) {
				elem.parentNode.selectedIndex;
			}

			return elem.selected === true;
		},

		"parent": function( elem ) {
			return !Expr.pseudos["empty"]( elem );
		},

		"empty": function( elem ) {
			// http://www.w3.org/TR/selectors/#empty-pseudo
			// :empty is only affected by element nodes and content nodes(including text(3), cdata(4)),
			//   not comment, processing instructions, or others
			// Thanks to Diego Perini for the nodeName shortcut
			//   Greater than "@" means alpha characters (specifically not starting with "#" or "?")
			var nodeType;
			elem = elem.firstChild;
			while ( elem ) {
				if ( elem.nodeName > "@" || (nodeType = elem.nodeType) === 3 || nodeType === 4 ) {
					return false;
				}
				elem = elem.nextSibling;
			}
			return true;
		},

		"header": function( elem ) {
			return rheader.test( elem.nodeName );
		},

		"text": function( elem ) {
			var type, attr;
			// IE6 and 7 will map elem.type to 'text' for new HTML5 types (search, etc)
			// use getAttribute instead to test this case
			return elem.nodeName.toLowerCase() === "input" &&
				(type = elem.type) === "text" &&
				( (attr = elem.getAttribute("type")) == null || attr.toLowerCase() === type );
		},

		// Input types
		"radio": createInputPseudo("radio"),
		"checkbox": createInputPseudo("checkbox"),
		"file": createInputPseudo("file"),
		"password": createInputPseudo("password"),
		"image": createInputPseudo("image"),

		"submit": createButtonPseudo("submit"),
		"reset": createButtonPseudo("reset"),

		"button": function( elem ) {
			var name = elem.nodeName.toLowerCase();
			return name === "input" && elem.type === "button" || name === "button";
		},

		"input": function( elem ) {
			return rinputs.test( elem.nodeName );
		},

		"focus": function( elem ) {
			var doc = elem.ownerDocument;
			return elem === doc.activeElement && (!doc.hasFocus || doc.hasFocus()) && !!(elem.type || elem.href || ~elem.tabIndex);
		},

		"active": function( elem ) {
			return elem === elem.ownerDocument.activeElement;
		},

		// Positional types
		"first": createPositionalPseudo(function() {
			return [ 0 ];
		}),

		"last": createPositionalPseudo(function( matchIndexes, length ) {
			return [ length - 1 ];
		}),

		"eq": createPositionalPseudo(function( matchIndexes, length, argument ) {
			return [ argument < 0 ? argument + length : argument ];
		}),

		"even": createPositionalPseudo(function( matchIndexes, length ) {
			for ( var i = 0; i < length; i += 2 ) {
				matchIndexes.push( i );
			}
			return matchIndexes;
		}),

		"odd": createPositionalPseudo(function( matchIndexes, length ) {
			for ( var i = 1; i < length; i += 2 ) {
				matchIndexes.push( i );
			}
			return matchIndexes;
		}),

		"lt": createPositionalPseudo(function( matchIndexes, length, argument ) {
			for ( var i = argument < 0 ? argument + length : argument; --i >= 0; ) {
				matchIndexes.push( i );
			}
			return matchIndexes;
		}),

		"gt": createPositionalPseudo(function( matchIndexes, length, argument ) {
			for ( var i = argument < 0 ? argument + length : argument; ++i < length; ) {
				matchIndexes.push( i );
			}
			return matchIndexes;
		})
	}
};

function siblingCheck( a, b, ret ) {
	if ( a === b ) {
		return ret;
	}

	var cur = a.nextSibling;

	while ( cur ) {
		if ( cur === b ) {
			return -1;
		}

		cur = cur.nextSibling;
	}

	return 1;
}

sortOrder = docElem.compareDocumentPosition ?
	function( a, b ) {
		if ( a === b ) {
			hasDuplicate = true;
			return 0;
		}

		return ( !a.compareDocumentPosition || !b.compareDocumentPosition ?
			a.compareDocumentPosition :
			a.compareDocumentPosition(b) & 4
		) ? -1 : 1;
	} :
	function( a, b ) {
		// The nodes are identical, we can exit early
		if ( a === b ) {
			hasDuplicate = true;
			return 0;

		// Fallback to using sourceIndex (in IE) if it's available on both nodes
		} else if ( a.sourceIndex && b.sourceIndex ) {
			return a.sourceIndex - b.sourceIndex;
		}

		var al, bl,
			ap = [],
			bp = [],
			aup = a.parentNode,
			bup = b.parentNode,
			cur = aup;

		// If the nodes are siblings (or identical) we can do a quick check
		if ( aup === bup ) {
			return siblingCheck( a, b );

		// If no parents were found then the nodes are disconnected
		} else if ( !aup ) {
			return -1;

		} else if ( !bup ) {
			return 1;
		}

		// Otherwise they're somewhere else in the tree so we need
		// to build up a full list of the parentNodes for comparison
		while ( cur ) {
			ap.unshift( cur );
			cur = cur.parentNode;
		}

		cur = bup;

		while ( cur ) {
			bp.unshift( cur );
			cur = cur.parentNode;
		}

		al = ap.length;
		bl = bp.length;

		// Start walking down the tree looking for a discrepancy
		for ( var i = 0; i < al && i < bl; i++ ) {
			if ( ap[i] !== bp[i] ) {
				return siblingCheck( ap[i], bp[i] );
			}
		}

		// We ended someplace up the tree so do a sibling check
		return i === al ?
			siblingCheck( a, bp[i], -1 ) :
			siblingCheck( ap[i], b, 1 );
	};

// Always assume the presence of duplicates if sort doesn't
// pass them to our comparison function (as in Google Chrome).
[0, 0].sort( sortOrder );
baseHasDuplicate = !hasDuplicate;

// Document sorting and removing duplicates
Sizzle.uniqueSort = function( results ) {
	var elem,
		duplicates = [],
		i = 1,
		j = 0;

	hasDuplicate = baseHasDuplicate;
	results.sort( sortOrder );

	if ( hasDuplicate ) {
		for ( ; (elem = results[i]); i++ ) {
			if ( elem === results[ i - 1 ] ) {
				j = duplicates.push( i );
			}
		}
		while ( j-- ) {
			results.splice( duplicates[ j ], 1 );
		}
	}

	return results;
};

Sizzle.error = function( msg ) {
	throw new Error( "Syntax error, unrecognized expression: " + msg );
};

function tokenize( selector, parseOnly ) {
	var matched, match, tokens, type,
		soFar, groups, preFilters,
		cached = tokenCache[ expando ][ selector + " " ];

	if ( cached ) {
		return parseOnly ? 0 : cached.slice( 0 );
	}

	soFar = selector;
	groups = [];
	preFilters = Expr.preFilter;

	while ( soFar ) {

		// Comma and first run
		if ( !matched || (match = rcomma.exec( soFar )) ) {
			if ( match ) {
				// Don't consume trailing commas as valid
				soFar = soFar.slice( match[0].length ) || soFar;
			}
			groups.push( tokens = [] );
		}

		matched = false;

		// Combinators
		if ( (match = rcombinators.exec( soFar )) ) {
			tokens.push( matched = new Token( match.shift() ) );
			soFar = soFar.slice( matched.length );

			// Cast descendant combinators to space
			matched.type = match[0].replace( rtrim, " " );
		}

		// Filters
		for ( type in Expr.filter ) {
			if ( (match = matchExpr[ type ].exec( soFar )) && (!preFilters[ type ] ||
				(match = preFilters[ type ]( match ))) ) {

				tokens.push( matched = new Token( match.shift() ) );
				soFar = soFar.slice( matched.length );
				matched.type = type;
				matched.matches = match;
			}
		}

		if ( !matched ) {
			break;
		}
	}

	// Return the length of the invalid excess
	// if we're just parsing
	// Otherwise, throw an error or return tokens
	return parseOnly ?
		soFar.length :
		soFar ?
			Sizzle.error( selector ) :
			// Cache the tokens
			tokenCache( selector, groups ).slice( 0 );
}

function addCombinator( matcher, combinator, base ) {
	var dir = combinator.dir,
		checkNonElements = base && combinator.dir === "parentNode",
		doneName = done++;

	return combinator.first ?
		// Check against closest ancestor/preceding element
		function( elem, context, xml ) {
			while ( (elem = elem[ dir ]) ) {
				if ( checkNonElements || elem.nodeType === 1  ) {
					return matcher( elem, context, xml );
				}
			}
		} :

		// Check against all ancestor/preceding elements
		function( elem, context, xml ) {
			// We can't set arbitrary data on XML nodes, so they don't benefit from dir caching
			if ( !xml ) {
				var cache,
					dirkey = dirruns + " " + doneName + " ",
					cachedkey = dirkey + cachedruns;
				while ( (elem = elem[ dir ]) ) {
					if ( checkNonElements || elem.nodeType === 1 ) {
						if ( (cache = elem[ expando ]) === cachedkey ) {
							return elem.sizset;
						} else if ( typeof cache === "string" && cache.indexOf(dirkey) === 0 ) {
							if ( elem.sizset ) {
								return elem;
							}
						} else {
							elem[ expando ] = cachedkey;
							if ( matcher( elem, context, xml ) ) {
								elem.sizset = true;
								return elem;
							}
							elem.sizset = false;
						}
					}
				}
			} else {
				while ( (elem = elem[ dir ]) ) {
					if ( checkNonElements || elem.nodeType === 1 ) {
						if ( matcher( elem, context, xml ) ) {
							return elem;
						}
					}
				}
			}
		};
}

function elementMatcher( matchers ) {
	return matchers.length > 1 ?
		function( elem, context, xml ) {
			var i = matchers.length;
			while ( i-- ) {
				if ( !matchers[i]( elem, context, xml ) ) {
					return false;
				}
			}
			return true;
		} :
		matchers[0];
}

function condense( unmatched, map, filter, context, xml ) {
	var elem,
		newUnmatched = [],
		i = 0,
		len = unmatched.length,
		mapped = map != null;

	for ( ; i < len; i++ ) {
		if ( (elem = unmatched[i]) ) {
			if ( !filter || filter( elem, context, xml ) ) {
				newUnmatched.push( elem );
				if ( mapped ) {
					map.push( i );
				}
			}
		}
	}

	return newUnmatched;
}

function setMatcher( preFilter, selector, matcher, postFilter, postFinder, postSelector ) {
	if ( postFilter && !postFilter[ expando ] ) {
		postFilter = setMatcher( postFilter );
	}
	if ( postFinder && !postFinder[ expando ] ) {
		postFinder = setMatcher( postFinder, postSelector );
	}
	return markFunction(function( seed, results, context, xml ) {
		var temp, i, elem,
			preMap = [],
			postMap = [],
			preexisting = results.length,

			// Get initial elements from seed or context
			elems = seed || multipleContexts( selector || "*", context.nodeType ? [ context ] : context, [] ),

			// Prefilter to get matcher input, preserving a map for seed-results synchronization
			matcherIn = preFilter && ( seed || !selector ) ?
				condense( elems, preMap, preFilter, context, xml ) :
				elems,

			matcherOut = matcher ?
				// If we have a postFinder, or filtered seed, or non-seed postFilter or preexisting results,
				postFinder || ( seed ? preFilter : preexisting || postFilter ) ?

					// ...intermediate processing is necessary
					[] :

					// ...otherwise use results directly
					results :
				matcherIn;

		// Find primary matches
		if ( matcher ) {
			matcher( matcherIn, matcherOut, context, xml );
		}

		// Apply postFilter
		if ( postFilter ) {
			temp = condense( matcherOut, postMap );
			postFilter( temp, [], context, xml );

			// Un-match failing elements by moving them back to matcherIn
			i = temp.length;
			while ( i-- ) {
				if ( (elem = temp[i]) ) {
					matcherOut[ postMap[i] ] = !(matcherIn[ postMap[i] ] = elem);
				}
			}
		}

		if ( seed ) {
			if ( postFinder || preFilter ) {
				if ( postFinder ) {
					// Get the final matcherOut by condensing this intermediate into postFinder contexts
					temp = [];
					i = matcherOut.length;
					while ( i-- ) {
						if ( (elem = matcherOut[i]) ) {
							// Restore matcherIn since elem is not yet a final match
							temp.push( (matcherIn[i] = elem) );
						}
					}
					postFinder( null, (matcherOut = []), temp, xml );
				}

				// Move matched elements from seed to results to keep them synchronized
				i = matcherOut.length;
				while ( i-- ) {
					if ( (elem = matcherOut[i]) &&
						(temp = postFinder ? indexOf.call( seed, elem ) : preMap[i]) > -1 ) {

						seed[temp] = !(results[temp] = elem);
					}
				}
			}

		// Add elements to results, through postFinder if defined
		} else {
			matcherOut = condense(
				matcherOut === results ?
					matcherOut.splice( preexisting, matcherOut.length ) :
					matcherOut
			);
			if ( postFinder ) {
				postFinder( null, results, matcherOut, xml );
			} else {
				push.apply( results, matcherOut );
			}
		}
	});
}

function matcherFromTokens( tokens ) {
	var checkContext, matcher, j,
		len = tokens.length,
		leadingRelative = Expr.relative[ tokens[0].type ],
		implicitRelative = leadingRelative || Expr.relative[" "],
		i = leadingRelative ? 1 : 0,

		// The foundational matcher ensures that elements are reachable from top-level context(s)
		matchContext = addCombinator( function( elem ) {
			return elem === checkContext;
		}, implicitRelative, true ),
		matchAnyContext = addCombinator( function( elem ) {
			return indexOf.call( checkContext, elem ) > -1;
		}, implicitRelative, true ),
		matchers = [ function( elem, context, xml ) {
			return ( !leadingRelative && ( xml || context !== outermostContext ) ) || (
				(checkContext = context).nodeType ?
					matchContext( elem, context, xml ) :
					matchAnyContext( elem, context, xml ) );
		} ];

	for ( ; i < len; i++ ) {
		if ( (matcher = Expr.relative[ tokens[i].type ]) ) {
			matchers = [ addCombinator( elementMatcher( matchers ), matcher ) ];
		} else {
			matcher = Expr.filter[ tokens[i].type ].apply( null, tokens[i].matches );

			// Return special upon seeing a positional matcher
			if ( matcher[ expando ] ) {
				// Find the next relative operator (if any) for proper handling
				j = ++i;
				for ( ; j < len; j++ ) {
					if ( Expr.relative[ tokens[j].type ] ) {
						break;
					}
				}
				return setMatcher(
					i > 1 && elementMatcher( matchers ),
					i > 1 && tokens.slice( 0, i - 1 ).join("").replace( rtrim, "$1" ),
					matcher,
					i < j && matcherFromTokens( tokens.slice( i, j ) ),
					j < len && matcherFromTokens( (tokens = tokens.slice( j )) ),
					j < len && tokens.join("")
				);
			}
			matchers.push( matcher );
		}
	}

	return elementMatcher( matchers );
}

function matcherFromGroupMatchers( elementMatchers, setMatchers ) {
	var bySet = setMatchers.length > 0,
		byElement = elementMatchers.length > 0,
		superMatcher = function( seed, context, xml, results, expandContext ) {
			var elem, j, matcher,
				setMatched = [],
				matchedCount = 0,
				i = "0",
				unmatched = seed && [],
				outermost = expandContext != null,
				contextBackup = outermostContext,
				// We must always have either seed elements or context
				elems = seed || byElement && Expr.find["TAG"]( "*", expandContext && context.parentNode || context ),
				// Nested matchers should use non-integer dirruns
				dirrunsUnique = (dirruns += contextBackup == null ? 1 : Math.E);

			if ( outermost ) {
				outermostContext = context !== document && context;
				cachedruns = superMatcher.el;
			}

			// Add elements passing elementMatchers directly to results
			for ( ; (elem = elems[i]) != null; i++ ) {
				if ( byElement && elem ) {
					for ( j = 0; (matcher = elementMatchers[j]); j++ ) {
						if ( matcher( elem, context, xml ) ) {
							results.push( elem );
							break;
						}
					}
					if ( outermost ) {
						dirruns = dirrunsUnique;
						cachedruns = ++superMatcher.el;
					}
				}

				// Track unmatched elements for set filters
				if ( bySet ) {
					// They will have gone through all possible matchers
					if ( (elem = !matcher && elem) ) {
						matchedCount--;
					}

					// Lengthen the array for every element, matched or not
					if ( seed ) {
						unmatched.push( elem );
					}
				}
			}

			// Apply set filters to unmatched elements
			matchedCount += i;
			if ( bySet && i !== matchedCount ) {
				for ( j = 0; (matcher = setMatchers[j]); j++ ) {
					matcher( unmatched, setMatched, context, xml );
				}

				if ( seed ) {
					// Reintegrate element matches to eliminate the need for sorting
					if ( matchedCount > 0 ) {
						while ( i-- ) {
							if ( !(unmatched[i] || setMatched[i]) ) {
								setMatched[i] = pop.call( results );
							}
						}
					}

					// Discard index placeholder values to get only actual matches
					setMatched = condense( setMatched );
				}

				// Add matches to results
				push.apply( results, setMatched );

				// Seedless set matches succeeding multiple successful matchers stipulate sorting
				if ( outermost && !seed && setMatched.length > 0 &&
					( matchedCount + setMatchers.length ) > 1 ) {

					Sizzle.uniqueSort( results );
				}
			}

			// Override manipulation of globals by nested matchers
			if ( outermost ) {
				dirruns = dirrunsUnique;
				outermostContext = contextBackup;
			}

			return unmatched;
		};

	superMatcher.el = 0;
	return bySet ?
		markFunction( superMatcher ) :
		superMatcher;
}

compile = Sizzle.compile = function( selector, group /* Internal Use Only */ ) {
	var i,
		setMatchers = [],
		elementMatchers = [],
		cached = compilerCache[ expando ][ selector + " " ];

	if ( !cached ) {
		// Generate a function of recursive functions that can be used to check each element
		if ( !group ) {
			group = tokenize( selector );
		}
		i = group.length;
		while ( i-- ) {
			cached = matcherFromTokens( group[i] );
			if ( cached[ expando ] ) {
				setMatchers.push( cached );
			} else {
				elementMatchers.push( cached );
			}
		}

		// Cache the compiled function
		cached = compilerCache( selector, matcherFromGroupMatchers( elementMatchers, setMatchers ) );
	}
	return cached;
};

function multipleContexts( selector, contexts, results ) {
	var i = 0,
		len = contexts.length;
	for ( ; i < len; i++ ) {
		Sizzle( selector, contexts[i], results );
	}
	return results;
}

function select( selector, context, results, seed, xml ) {
	var i, tokens, token, type, find,
		match = tokenize( selector ),
		j = match.length;

	if ( !seed ) {
		// Try to minimize operations if there is only one group
		if ( match.length === 1 ) {

			// Take a shortcut and set the context if the root selector is an ID
			tokens = match[0] = match[0].slice( 0 );
			if ( tokens.length > 2 && (token = tokens[0]).type === "ID" &&
					context.nodeType === 9 && !xml &&
					Expr.relative[ tokens[1].type ] ) {

				context = Expr.find["ID"]( token.matches[0].replace( rbackslash, "" ), context, xml )[0];
				if ( !context ) {
					return results;
				}

				selector = selector.slice( tokens.shift().length );
			}

			// Fetch a seed set for right-to-left matching
			for ( i = matchExpr["POS"].test( selector ) ? -1 : tokens.length - 1; i >= 0; i-- ) {
				token = tokens[i];

				// Abort if we hit a combinator
				if ( Expr.relative[ (type = token.type) ] ) {
					break;
				}
				if ( (find = Expr.find[ type ]) ) {
					// Search, expanding context for leading sibling combinators
					if ( (seed = find(
						token.matches[0].replace( rbackslash, "" ),
						rsibling.test( tokens[0].type ) && context.parentNode || context,
						xml
					)) ) {

						// If seed is empty or no tokens remain, we can return early
						tokens.splice( i, 1 );
						selector = seed.length && tokens.join("");
						if ( !selector ) {
							push.apply( results, slice.call( seed, 0 ) );
							return results;
						}

						break;
					}
				}
			}
		}
	}

	// Compile and execute a filtering function
	// Provide `match` to avoid retokenization if we modified the selector above
	compile( selector, match )(
		seed,
		context,
		xml,
		results,
		rsibling.test( selector )
	);
	return results;
}

if ( document.querySelectorAll ) {
	(function() {
		var disconnectedMatch,
			oldSelect = select,
			rescape = /'|\\/g,
			rattributeQuotes = /\=[\x20\t\r\n\f]*([^'"\]]*)[\x20\t\r\n\f]*\]/g,

			// qSa(:focus) reports false when true (Chrome 21), no need to also add to buggyMatches since matches checks buggyQSA
			// A support test would require too much code (would include document ready)
			rbuggyQSA = [ ":focus" ],

			// matchesSelector(:active) reports false when true (IE9/Opera 11.5)
			// A support test would require too much code (would include document ready)
			// just skip matchesSelector for :active
			rbuggyMatches = [ ":active" ],
			matches = docElem.matchesSelector ||
				docElem.mozMatchesSelector ||
				docElem.webkitMatchesSelector ||
				docElem.oMatchesSelector ||
				docElem.msMatchesSelector;

		// Build QSA regex
		// Regex strategy adopted from Diego Perini
		assert(function( div ) {
			// Select is set to empty string on purpose
			// This is to test IE's treatment of not explictly
			// setting a boolean content attribute,
			// since its presence should be enough
			// http://bugs.jquery.com/ticket/12359
			div.innerHTML = "<select><option selected=''></option></select>";

			// IE8 - Some boolean attributes are not treated correctly
			if ( !div.querySelectorAll("[selected]").length ) {
				rbuggyQSA.push( "\\[" + whitespace + "*(?:checked|disabled|ismap|multiple|readonly|selected|value)" );
			}

			// Webkit/Opera - :checked should return selected option elements
			// http://www.w3.org/TR/2011/REC-css3-selectors-20110929/#checked
			// IE8 throws error here (do not put tests after this one)
			if ( !div.querySelectorAll(":checked").length ) {
				rbuggyQSA.push(":checked");
			}
		});

		assert(function( div ) {

			// Opera 10-12/IE9 - ^= $= *= and empty values
			// Should not select anything
			div.innerHTML = "<p test=''></p>";
			if ( div.querySelectorAll("[test^='']").length ) {
				rbuggyQSA.push( "[*^$]=" + whitespace + "*(?:\"\"|'')" );
			}

			// FF 3.5 - :enabled/:disabled and hidden elements (hidden elements are still enabled)
			// IE8 throws error here (do not put tests after this one)
			div.innerHTML = "<input type='hidden'/>";
			if ( !div.querySelectorAll(":enabled").length ) {
				rbuggyQSA.push(":enabled", ":disabled");
			}
		});

		// rbuggyQSA always contains :focus, so no need for a length check
		rbuggyQSA = /* rbuggyQSA.length && */ new RegExp( rbuggyQSA.join("|") );

		select = function( selector, context, results, seed, xml ) {
			// Only use querySelectorAll when not filtering,
			// when this is not xml,
			// and when no QSA bugs apply
			if ( !seed && !xml && !rbuggyQSA.test( selector ) ) {
				var groups, i,
					old = true,
					nid = expando,
					newContext = context,
					newSelector = context.nodeType === 9 && selector;

				// qSA works strangely on Element-rooted queries
				// We can work around this by specifying an extra ID on the root
				// and working up from there (Thanks to Andrew Dupont for the technique)
				// IE 8 doesn't work on object elements
				if ( context.nodeType === 1 && context.nodeName.toLowerCase() !== "object" ) {
					groups = tokenize( selector );

					if ( (old = context.getAttribute("id")) ) {
						nid = old.replace( rescape, "\\$&" );
					} else {
						context.setAttribute( "id", nid );
					}
					nid = "[id='" + nid + "'] ";

					i = groups.length;
					while ( i-- ) {
						groups[i] = nid + groups[i].join("");
					}
					newContext = rsibling.test( selector ) && context.parentNode || context;
					newSelector = groups.join(",");
				}

				if ( newSelector ) {
					try {
						push.apply( results, slice.call( newContext.querySelectorAll(
							newSelector
						), 0 ) );
						return results;
					} catch(qsaError) {
					} finally {
						if ( !old ) {
							context.removeAttribute("id");
						}
					}
				}
			}

			return oldSelect( selector, context, results, seed, xml );
		};

		if ( matches ) {
			assert(function( div ) {
				// Check to see if it's possible to do matchesSelector
				// on a disconnected node (IE 9)
				disconnectedMatch = matches.call( div, "div" );

				// This should fail with an exception
				// Gecko does not error, returns false instead
				try {
					matches.call( div, "[test!='']:sizzle" );
					rbuggyMatches.push( "!=", pseudos );
				} catch ( e ) {}
			});

			// rbuggyMatches always contains :active and :focus, so no need for a length check
			rbuggyMatches = /* rbuggyMatches.length && */ new RegExp( rbuggyMatches.join("|") );

			Sizzle.matchesSelector = function( elem, expr ) {
				// Make sure that attribute selectors are quoted
				expr = expr.replace( rattributeQuotes, "='$1']" );

				// rbuggyMatches always contains :active, so no need for an existence check
				if ( !isXML( elem ) && !rbuggyMatches.test( expr ) && !rbuggyQSA.test( expr ) ) {
					try {
						var ret = matches.call( elem, expr );

						// IE 9's matchesSelector returns false on disconnected nodes
						if ( ret || disconnectedMatch ||
								// As well, disconnected nodes are said to be in a document
								// fragment in IE 9
								elem.document && elem.document.nodeType !== 11 ) {
							return ret;
						}
					} catch(e) {}
				}

				return Sizzle( expr, null, null, [ elem ] ).length > 0;
			};
		}
	})();
}

// Deprecated
Expr.pseudos["nth"] = Expr.pseudos["eq"];

// Back-compat
function setFilters() {}
Expr.filters = setFilters.prototype = Expr.pseudos;
Expr.setFilters = new setFilters();

// Override sizzle attribute retrieval
Sizzle.attr = jQuery.attr;
jQuery.find = Sizzle;
jQuery.expr = Sizzle.selectors;
jQuery.expr[":"] = jQuery.expr.pseudos;
jQuery.unique = Sizzle.uniqueSort;
jQuery.text = Sizzle.getText;
jQuery.isXMLDoc = Sizzle.isXML;
jQuery.contains = Sizzle.contains;


})( window );
var runtil = /Until$/,
	rparentsprev = /^(?:parents|prev(?:Until|All))/,
	isSimple = /^.[^:#\[\.,]*$/,
	rneedsContext = jQuery.expr.match.needsContext,
	// methods guaranteed to produce a unique set when starting from a unique set
	guaranteedUnique = {
		children: true,
		contents: true,
		next: true,
		prev: true
	};

jQuery.fn.extend({
	find: function( selector ) {
		var i, l, length, n, r, ret,
			self = this;

		if ( typeof selector !== "string" ) {
			return jQuery( selector ).filter(function() {
				for ( i = 0, l = self.length; i < l; i++ ) {
					if ( jQuery.contains( self[ i ], this ) ) {
						return true;
					}
				}
			});
		}

		ret = this.pushStack( "", "find", selector );

		for ( i = 0, l = this.length; i < l; i++ ) {
			length = ret.length;
			jQuery.find( selector, this[i], ret );

			if ( i > 0 ) {
				// Make sure that the results are unique
				for ( n = length; n < ret.length; n++ ) {
					for ( r = 0; r < length; r++ ) {
						if ( ret[r] === ret[n] ) {
							ret.splice(n--, 1);
							break;
						}
					}
				}
			}
		}

		return ret;
	},

	has: function( target ) {
		var i,
			targets = jQuery( target, this ),
			len = targets.length;

		return this.filter(function() {
			for ( i = 0; i < len; i++ ) {
				if ( jQuery.contains( this, targets[i] ) ) {
					return true;
				}
			}
		});
	},

	not: function( selector ) {
		return this.pushStack( winnow(this, selector, false), "not", selector);
	},

	filter: function( selector ) {
		return this.pushStack( winnow(this, selector, true), "filter", selector );
	},

	is: function( selector ) {
		return !!selector && (
			typeof selector === "string" ?
				// If this is a positional/relative selector, check membership in the returned set
				// so $("p:first").is("p:last") won't return true for a doc with two "p".
				rneedsContext.test( selector ) ?
					jQuery( selector, this.context ).index( this[0] ) >= 0 :
					jQuery.filter( selector, this ).length > 0 :
				this.filter( selector ).length > 0 );
	},

	closest: function( selectors, context ) {
		var cur,
			i = 0,
			l = this.length,
			ret = [],
			pos = rneedsContext.test( selectors ) || typeof selectors !== "string" ?
				jQuery( selectors, context || this.context ) :
				0;

		for ( ; i < l; i++ ) {
			cur = this[i];

			while ( cur && cur.ownerDocument && cur !== context && cur.nodeType !== 11 ) {
				if ( pos ? pos.index(cur) > -1 : jQuery.find.matchesSelector(cur, selectors) ) {
					ret.push( cur );
					break;
				}
				cur = cur.parentNode;
			}
		}

		ret = ret.length > 1 ? jQuery.unique( ret ) : ret;

		return this.pushStack( ret, "closest", selectors );
	},

	// Determine the position of an element within
	// the matched set of elements
	index: function( elem ) {

		// No argument, return index in parent
		if ( !elem ) {
			return ( this[0] && this[0].parentNode ) ? this.prevAll().length : -1;
		}

		// index in selector
		if ( typeof elem === "string" ) {
			return jQuery.inArray( this[0], jQuery( elem ) );
		}

		// Locate the position of the desired element
		return jQuery.inArray(
			// If it receives a jQuery object, the first element is used
			elem.jquery ? elem[0] : elem, this );
	},

	add: function( selector, context ) {
		var set = typeof selector === "string" ?
				jQuery( selector, context ) :
				jQuery.makeArray( selector && selector.nodeType ? [ selector ] : selector ),
			all = jQuery.merge( this.get(), set );

		return this.pushStack( isDisconnected( set[0] ) || isDisconnected( all[0] ) ?
			all :
			jQuery.unique( all ) );
	},

	addBack: function( selector ) {
		return this.add( selector == null ?
			this.prevObject : this.prevObject.filter(selector)
		);
	}
});

jQuery.fn.andSelf = jQuery.fn.addBack;

// A painfully simple check to see if an element is disconnected
// from a document (should be improved, where feasible).
function isDisconnected( node ) {
	return !node || !node.parentNode || node.parentNode.nodeType === 11;
}

function sibling( cur, dir ) {
	do {
		cur = cur[ dir ];
	} while ( cur && cur.nodeType !== 1 );

	return cur;
}

jQuery.each({
	parent: function( elem ) {
		var parent = elem.parentNode;
		return parent && parent.nodeType !== 11 ? parent : null;
	},
	parents: function( elem ) {
		return jQuery.dir( elem, "parentNode" );
	},
	parentsUntil: function( elem, i, until ) {
		return jQuery.dir( elem, "parentNode", until );
	},
	next: function( elem ) {
		return sibling( elem, "nextSibling" );
	},
	prev: function( elem ) {
		return sibling( elem, "previousSibling" );
	},
	nextAll: function( elem ) {
		return jQuery.dir( elem, "nextSibling" );
	},
	prevAll: function( elem ) {
		return jQuery.dir( elem, "previousSibling" );
	},
	nextUntil: function( elem, i, until ) {
		return jQuery.dir( elem, "nextSibling", until );
	},
	prevUntil: function( elem, i, until ) {
		return jQuery.dir( elem, "previousSibling", until );
	},
	siblings: function( elem ) {
		return jQuery.sibling( ( elem.parentNode || {} ).firstChild, elem );
	},
	children: function( elem ) {
		return jQuery.sibling( elem.firstChild );
	},
	contents: function( elem ) {
		return jQuery.nodeName( elem, "iframe" ) ?
			elem.contentDocument || elem.contentWindow.document :
			jQuery.merge( [], elem.childNodes );
	}
}, function( name, fn ) {
	jQuery.fn[ name ] = function( until, selector ) {
		var ret = jQuery.map( this, fn, until );

		if ( !runtil.test( name ) ) {
			selector = until;
		}

		if ( selector && typeof selector === "string" ) {
			ret = jQuery.filter( selector, ret );
		}

		ret = this.length > 1 && !guaranteedUnique[ name ] ? jQuery.unique( ret ) : ret;

		if ( this.length > 1 && rparentsprev.test( name ) ) {
			ret = ret.reverse();
		}

		return this.pushStack( ret, name, core_slice.call( arguments ).join(",") );
	};
});

jQuery.extend({
	filter: function( expr, elems, not ) {
		if ( not ) {
			expr = ":not(" + expr + ")";
		}

		return elems.length === 1 ?
			jQuery.find.matchesSelector(elems[0], expr) ? [ elems[0] ] : [] :
			jQuery.find.matches(expr, elems);
	},

	dir: function( elem, dir, until ) {
		var matched = [],
			cur = elem[ dir ];

		while ( cur && cur.nodeType !== 9 && (until === undefined || cur.nodeType !== 1 || !jQuery( cur ).is( until )) ) {
			if ( cur.nodeType === 1 ) {
				matched.push( cur );
			}
			cur = cur[dir];
		}
		return matched;
	},

	sibling: function( n, elem ) {
		var r = [];

		for ( ; n; n = n.nextSibling ) {
			if ( n.nodeType === 1 && n !== elem ) {
				r.push( n );
			}
		}

		return r;
	}
});

// Implement the identical functionality for filter and not
function winnow( elements, qualifier, keep ) {

	// Can't pass null or undefined to indexOf in Firefox 4
	// Set to 0 to skip string check
	qualifier = qualifier || 0;

	if ( jQuery.isFunction( qualifier ) ) {
		return jQuery.grep(elements, function( elem, i ) {
			var retVal = !!qualifier.call( elem, i, elem );
			return retVal === keep;
		});

	} else if ( qualifier.nodeType ) {
		return jQuery.grep(elements, function( elem, i ) {
			return ( elem === qualifier ) === keep;
		});

	} else if ( typeof qualifier === "string" ) {
		var filtered = jQuery.grep(elements, function( elem ) {
			return elem.nodeType === 1;
		});

		if ( isSimple.test( qualifier ) ) {
			return jQuery.filter(qualifier, filtered, !keep);
		} else {
			qualifier = jQuery.filter( qualifier, filtered );
		}
	}

	return jQuery.grep(elements, function( elem, i ) {
		return ( jQuery.inArray( elem, qualifier ) >= 0 ) === keep;
	});
}
function createSafeFragment( document ) {
	var list = nodeNames.split( "|" ),
	safeFrag = document.createDocumentFragment();

	if ( safeFrag.createElement ) {
		while ( list.length ) {
			safeFrag.createElement(
				list.pop()
			);
		}
	}
	return safeFrag;
}

var nodeNames = "abbr|article|aside|audio|bdi|canvas|data|datalist|details|figcaption|figure|footer|" +
		"header|hgroup|mark|meter|nav|output|progress|section|summary|time|video",
	rinlinejQuery = / jQuery\d+="(?:null|\d+)"/g,
	rleadingWhitespace = /^\s+/,
	rxhtmlTag = /<(?!area|br|col|embed|hr|img|input|link|meta|param)(([\w:]+)[^>]*)\/>/gi,
	rtagName = /<([\w:]+)/,
	rtbody = /<tbody/i,
	rhtml = /<|&#?\w+;/,
	rnoInnerhtml = /<(?:script|style|link)/i,
	rnocache = /<(?:script|object|embed|option|style)/i,
	rnoshimcache = new RegExp("<(?:" + nodeNames + ")[\\s/>]", "i"),
	rcheckableType = /^(?:checkbox|radio)$/,
	// checked="checked" or checked
	rchecked = /checked\s*(?:[^=]|=\s*.checked.)/i,
	rscriptType = /\/(java|ecma)script/i,
	rcleanScript = /^\s*<!(?:\[CDATA\[|\-\-)|[\]\-]{2}>\s*$/g,
	wrapMap = {
		option: [ 1, "<select multiple='multiple'>", "</select>" ],
		legend: [ 1, "<fieldset>", "</fieldset>" ],
		thead: [ 1, "<table>", "</table>" ],
		tr: [ 2, "<table><tbody>", "</tbody></table>" ],
		td: [ 3, "<table><tbody><tr>", "</tr></tbody></table>" ],
		col: [ 2, "<table><tbody></tbody><colgroup>", "</colgroup></table>" ],
		area: [ 1, "<map>", "</map>" ],
		_default: [ 0, "", "" ]
	},
	safeFragment = createSafeFragment( document ),
	fragmentDiv = safeFragment.appendChild( document.createElement("div") );

wrapMap.optgroup = wrapMap.option;
wrapMap.tbody = wrapMap.tfoot = wrapMap.colgroup = wrapMap.caption = wrapMap.thead;
wrapMap.th = wrapMap.td;

// IE6-8 can't serialize link, script, style, or any html5 (NoScope) tags,
// unless wrapped in a div with non-breaking characters in front of it.
if ( !jQuery.support.htmlSerialize ) {
	wrapMap._default = [ 1, "X<div>", "</div>" ];
}

jQuery.fn.extend({
	text: function( value ) {
		return jQuery.access( this, function( value ) {
			return value === undefined ?
				jQuery.text( this ) :
				this.empty().append( ( this[0] && this[0].ownerDocument || document ).createTextNode( value ) );
		}, null, value, arguments.length );
	},

	wrapAll: function( html ) {
		if ( jQuery.isFunction( html ) ) {
			return this.each(function(i) {
				jQuery(this).wrapAll( html.call(this, i) );
			});
		}

		if ( this[0] ) {
			// The elements to wrap the target around
			var wrap = jQuery( html, this[0].ownerDocument ).eq(0).clone(true);

			if ( this[0].parentNode ) {
				wrap.insertBefore( this[0] );
			}

			wrap.map(function() {
				var elem = this;

				while ( elem.firstChild && elem.firstChild.nodeType === 1 ) {
					elem = elem.firstChild;
				}

				return elem;
			}).append( this );
		}

		return this;
	},

	wrapInner: function( html ) {
		if ( jQuery.isFunction( html ) ) {
			return this.each(function(i) {
				jQuery(this).wrapInner( html.call(this, i) );
			});
		}

		return this.each(function() {
			var self = jQuery( this ),
				contents = self.contents();

			if ( contents.length ) {
				contents.wrapAll( html );

			} else {
				self.append( html );
			}
		});
	},

	wrap: function( html ) {
		var isFunction = jQuery.isFunction( html );

		return this.each(function(i) {
			jQuery( this ).wrapAll( isFunction ? html.call(this, i) : html );
		});
	},

	unwrap: function() {
		return this.parent().each(function() {
			if ( !jQuery.nodeName( this, "body" ) ) {
				jQuery( this ).replaceWith( this.childNodes );
			}
		}).end();
	},

	append: function() {
		return this.domManip(arguments, true, function( elem ) {
			if ( this.nodeType === 1 || this.nodeType === 11 ) {
				this.appendChild( elem );
			}
		});
	},

	prepend: function() {
		return this.domManip(arguments, true, function( elem ) {
			if ( this.nodeType === 1 || this.nodeType === 11 ) {
				this.insertBefore( elem, this.firstChild );
			}
		});
	},

	before: function() {
		if ( !isDisconnected( this[0] ) ) {
			return this.domManip(arguments, false, function( elem ) {
				this.parentNode.insertBefore( elem, this );
			});
		}

		if ( arguments.length ) {
			var set = jQuery.clean( arguments );
			return this.pushStack( jQuery.merge( set, this ), "before", this.selector );
		}
	},

	after: function() {
		if ( !isDisconnected( this[0] ) ) {
			return this.domManip(arguments, false, function( elem ) {
				this.parentNode.insertBefore( elem, this.nextSibling );
			});
		}

		if ( arguments.length ) {
			var set = jQuery.clean( arguments );
			return this.pushStack( jQuery.merge( this, set ), "after", this.selector );
		}
	},

	// keepData is for internal use only--do not document
	remove: function( selector, keepData ) {
		var elem,
			i = 0;

		for ( ; (elem = this[i]) != null; i++ ) {
			if ( !selector || jQuery.filter( selector, [ elem ] ).length ) {
				if ( !keepData && elem.nodeType === 1 ) {
					jQuery.cleanData( elem.getElementsByTagName("*") );
					jQuery.cleanData( [ elem ] );
				}

				if ( elem.parentNode ) {
					elem.parentNode.removeChild( elem );
				}
			}
		}

		return this;
	},

	empty: function() {
		var elem,
			i = 0;

		for ( ; (elem = this[i]) != null; i++ ) {
			// Remove element nodes and prevent memory leaks
			if ( elem.nodeType === 1 ) {
				jQuery.cleanData( elem.getElementsByTagName("*") );
			}

			// Remove any remaining nodes
			while ( elem.firstChild ) {
				elem.removeChild( elem.firstChild );
			}
		}

		return this;
	},

	clone: function( dataAndEvents, deepDataAndEvents ) {
		dataAndEvents = dataAndEvents == null ? false : dataAndEvents;
		deepDataAndEvents = deepDataAndEvents == null ? dataAndEvents : deepDataAndEvents;

		return this.map( function () {
			return jQuery.clone( this, dataAndEvents, deepDataAndEvents );
		});
	},

	html: function( value ) {
		return jQuery.access( this, function( value ) {
			var elem = this[0] || {},
				i = 0,
				l = this.length;

			if ( value === undefined ) {
				return elem.nodeType === 1 ?
					elem.innerHTML.replace( rinlinejQuery, "" ) :
					undefined;
			}

			// See if we can take a shortcut and just use innerHTML
			if ( typeof value === "string" && !rnoInnerhtml.test( value ) &&
				( jQuery.support.htmlSerialize || !rnoshimcache.test( value )  ) &&
				( jQuery.support.leadingWhitespace || !rleadingWhitespace.test( value ) ) &&
				!wrapMap[ ( rtagName.exec( value ) || ["", ""] )[1].toLowerCase() ] ) {

				value = value.replace( rxhtmlTag, "<$1></$2>" );

				try {
					for (; i < l; i++ ) {
						// Remove element nodes and prevent memory leaks
						elem = this[i] || {};
						if ( elem.nodeType === 1 ) {
							jQuery.cleanData( elem.getElementsByTagName( "*" ) );
							elem.innerHTML = value;
						}
					}

					elem = 0;

				// If using innerHTML throws an exception, use the fallback method
				} catch(e) {}
			}

			if ( elem ) {
				this.empty().append( value );
			}
		}, null, value, arguments.length );
	},

	replaceWith: function( value ) {
		if ( !isDisconnected( this[0] ) ) {
			// Make sure that the elements are removed from the DOM before they are inserted
			// this can help fix replacing a parent with child elements
			if ( jQuery.isFunction( value ) ) {
				return this.each(function(i) {
					var self = jQuery(this), old = self.html();
					self.replaceWith( value.call( this, i, old ) );
				});
			}

			if ( typeof value !== "string" ) {
				value = jQuery( value ).detach();
			}

			return this.each(function() {
				var next = this.nextSibling,
					parent = this.parentNode;

				jQuery( this ).remove();

				if ( next ) {
					jQuery(next).before( value );
				} else {
					jQuery(parent).append( value );
				}
			});
		}

		return this.length ?
			this.pushStack( jQuery(jQuery.isFunction(value) ? value() : value), "replaceWith", value ) :
			this;
	},

	detach: function( selector ) {
		return this.remove( selector, true );
	},

	domManip: function( args, table, callback ) {

		// Flatten any nested arrays
		args = [].concat.apply( [], args );

		var results, first, fragment, iNoClone,
			i = 0,
			value = args[0],
			scripts = [],
			l = this.length;

		// We can't cloneNode fragments that contain checked, in WebKit
		if ( !jQuery.support.checkClone && l > 1 && typeof value === "string" && rchecked.test( value ) ) {
			return this.each(function() {
				jQuery(this).domManip( args, table, callback );
			});
		}

		if ( jQuery.isFunction(value) ) {
			return this.each(function(i) {
				var self = jQuery(this);
				args[0] = value.call( this, i, table ? self.html() : undefined );
				self.domManip( args, table, callback );
			});
		}

		if ( this[0] ) {
			results = jQuery.buildFragment( args, this, scripts );
			fragment = results.fragment;
			first = fragment.firstChild;

			if ( fragment.childNodes.length === 1 ) {
				fragment = first;
			}

			if ( first ) {
				table = table && jQuery.nodeName( first, "tr" );

				// Use the original fragment for the last item instead of the first because it can end up
				// being emptied incorrectly in certain situations (#8070).
				// Fragments from the fragment cache must always be cloned and never used in place.
				for ( iNoClone = results.cacheable || l - 1; i < l; i++ ) {
					callback.call(
						table && jQuery.nodeName( this[i], "table" ) ?
							findOrAppend( this[i], "tbody" ) :
							this[i],
						i === iNoClone ?
							fragment :
							jQuery.clone( fragment, true, true )
					);
				}
			}

			// Fix #11809: Avoid leaking memory
			fragment = first = null;

			if ( scripts.length ) {
				jQuery.each( scripts, function( i, elem ) {
					if ( elem.src ) {
						if ( jQuery.ajax ) {
							jQuery.ajax({
								url: elem.src,
								type: "GET",
								dataType: "script",
								async: false,
								global: false,
								"throws": true
							});
						} else {
							jQuery.error("no ajax");
						}
					} else {
						jQuery.globalEval( ( elem.text || elem.textContent || elem.innerHTML || "" ).replace( rcleanScript, "" ) );
					}

					if ( elem.parentNode ) {
						elem.parentNode.removeChild( elem );
					}
				});
			}
		}

		return this;
	}
});

function findOrAppend( elem, tag ) {
	return elem.getElementsByTagName( tag )[0] || elem.appendChild( elem.ownerDocument.createElement( tag ) );
}

function cloneCopyEvent( src, dest ) {

	if ( dest.nodeType !== 1 || !jQuery.hasData( src ) ) {
		return;
	}

	var type, i, l,
		oldData = jQuery._data( src ),
		curData = jQuery._data( dest, oldData ),
		events = oldData.events;

	if ( events ) {
		delete curData.handle;
		curData.events = {};

		for ( type in events ) {
			for ( i = 0, l = events[ type ].length; i < l; i++ ) {
				jQuery.event.add( dest, type, events[ type ][ i ] );
			}
		}
	}

	// make the cloned public data object a copy from the original
	if ( curData.data ) {
		curData.data = jQuery.extend( {}, curData.data );
	}
}

function cloneFixAttributes( src, dest ) {
	var nodeName;

	// We do not need to do anything for non-Elements
	if ( dest.nodeType !== 1 ) {
		return;
	}

	// clearAttributes removes the attributes, which we don't want,
	// but also removes the attachEvent events, which we *do* want
	if ( dest.clearAttributes ) {
		dest.clearAttributes();
	}

	// mergeAttributes, in contrast, only merges back on the
	// original attributes, not the events
	if ( dest.mergeAttributes ) {
		dest.mergeAttributes( src );
	}

	nodeName = dest.nodeName.toLowerCase();

	if ( nodeName === "object" ) {
		// IE6-10 improperly clones children of object elements using classid.
		// IE10 throws NoModificationAllowedError if parent is null, #12132.
		if ( dest.parentNode ) {
			dest.outerHTML = src.outerHTML;
		}

		// This path appears unavoidable for IE9. When cloning an object
		// element in IE9, the outerHTML strategy above is not sufficient.
		// If the src has innerHTML and the destination does not,
		// copy the src.innerHTML into the dest.innerHTML. #10324
		if ( jQuery.support.html5Clone && (src.innerHTML && !jQuery.trim(dest.innerHTML)) ) {
			dest.innerHTML = src.innerHTML;
		}

	} else if ( nodeName === "input" && rcheckableType.test( src.type ) ) {
		// IE6-8 fails to persist the checked state of a cloned checkbox
		// or radio button. Worse, IE6-7 fail to give the cloned element
		// a checked appearance if the defaultChecked value isn't also set

		dest.defaultChecked = dest.checked = src.checked;

		// IE6-7 get confused and end up setting the value of a cloned
		// checkbox/radio button to an empty string instead of "on"
		if ( dest.value !== src.value ) {
			dest.value = src.value;
		}

	// IE6-8 fails to return the selected option to the default selected
	// state when cloning options
	} else if ( nodeName === "option" ) {
		dest.selected = src.defaultSelected;

	// IE6-8 fails to set the defaultValue to the correct value when
	// cloning other types of input fields
	} else if ( nodeName === "input" || nodeName === "textarea" ) {
		dest.defaultValue = src.defaultValue;

	// IE blanks contents when cloning scripts
	} else if ( nodeName === "script" && dest.text !== src.text ) {
		dest.text = src.text;
	}

	// Event data gets referenced instead of copied if the expando
	// gets copied too
	dest.removeAttribute( jQuery.expando );
}

jQuery.buildFragment = function( args, context, scripts ) {
	var fragment, cacheable, cachehit,
		first = args[ 0 ];

	// Set context from what may come in as undefined or a jQuery collection or a node
	// Updated to fix #12266 where accessing context[0] could throw an exception in IE9/10 &
	// also doubles as fix for #8950 where plain objects caused createDocumentFragment exception
	context = context || document;
	context = !context.nodeType && context[0] || context;
	context = context.ownerDocument || context;

	// Only cache "small" (1/2 KB) HTML strings that are associated with the main document
	// Cloning options loses the selected state, so don't cache them
	// IE 6 doesn't like it when you put <object> or <embed> elements in a fragment
	// Also, WebKit does not clone 'checked' attributes on cloneNode, so don't cache
	// Lastly, IE6,7,8 will not correctly reuse cached fragments that were created from unknown elems #10501
	if ( args.length === 1 && typeof first === "string" && first.length < 512 && context === document &&
		first.charAt(0) === "<" && !rnocache.test( first ) &&
		(jQuery.support.checkClone || !rchecked.test( first )) &&
		(jQuery.support.html5Clone || !rnoshimcache.test( first )) ) {

		// Mark cacheable and look for a hit
		cacheable = true;
		fragment = jQuery.fragments[ first ];
		cachehit = fragment !== undefined;
	}

	if ( !fragment ) {
		fragment = context.createDocumentFragment();
		jQuery.clean( args, context, fragment, scripts );

		// Update the cache, but only store false
		// unless this is a second parsing of the same content
		if ( cacheable ) {
			jQuery.fragments[ first ] = cachehit && fragment;
		}
	}

	return { fragment: fragment, cacheable: cacheable };
};

jQuery.fragments = {};

jQuery.each({
	appendTo: "append",
	prependTo: "prepend",
	insertBefore: "before",
	insertAfter: "after",
	replaceAll: "replaceWith"
}, function( name, original ) {
	jQuery.fn[ name ] = function( selector ) {
		var elems,
			i = 0,
			ret = [],
			insert = jQuery( selector ),
			l = insert.length,
			parent = this.length === 1 && this[0].parentNode;

		if ( (parent == null || parent && parent.nodeType === 11 && parent.childNodes.length === 1) && l === 1 ) {
			insert[ original ]( this[0] );
			return this;
		} else {
			for ( ; i < l; i++ ) {
				elems = ( i > 0 ? this.clone(true) : this ).get();
				jQuery( insert[i] )[ original ]( elems );
				ret = ret.concat( elems );
			}

			return this.pushStack( ret, name, insert.selector );
		}
	};
});

function getAll( elem ) {
	if ( typeof elem.getElementsByTagName !== "undefined" ) {
		return elem.getElementsByTagName( "*" );

	} else if ( typeof elem.querySelectorAll !== "undefined" ) {
		return elem.querySelectorAll( "*" );

	} else {
		return [];
	}
}

// Used in clean, fixes the defaultChecked property
function fixDefaultChecked( elem ) {
	if ( rcheckableType.test( elem.type ) ) {
		elem.defaultChecked = elem.checked;
	}
}

jQuery.extend({
	clone: function( elem, dataAndEvents, deepDataAndEvents ) {
		var srcElements,
			destElements,
			i,
			clone;

		if ( jQuery.support.html5Clone || jQuery.isXMLDoc(elem) || !rnoshimcache.test( "<" + elem.nodeName + ">" ) ) {
			clone = elem.cloneNode( true );

		// IE<=8 does not properly clone detached, unknown element nodes
		} else {
			fragmentDiv.innerHTML = elem.outerHTML;
			fragmentDiv.removeChild( clone = fragmentDiv.firstChild );
		}

		if ( (!jQuery.support.noCloneEvent || !jQuery.support.noCloneChecked) &&
				(elem.nodeType === 1 || elem.nodeType === 11) && !jQuery.isXMLDoc(elem) ) {
			// IE copies events bound via attachEvent when using cloneNode.
			// Calling detachEvent on the clone will also remove the events
			// from the original. In order to get around this, we use some
			// proprietary methods to clear the events. Thanks to MooTools
			// guys for this hotness.

			cloneFixAttributes( elem, clone );

			// Using Sizzle here is crazy slow, so we use getElementsByTagName instead
			srcElements = getAll( elem );
			destElements = getAll( clone );

			// Weird iteration because IE will replace the length property
			// with an element if you are cloning the body and one of the
			// elements on the page has a name or id of "length"
			for ( i = 0; srcElements[i]; ++i ) {
				// Ensure that the destination node is not null; Fixes #9587
				if ( destElements[i] ) {
					cloneFixAttributes( srcElements[i], destElements[i] );
				}
			}
		}

		// Copy the events from the original to the clone
		if ( dataAndEvents ) {
			cloneCopyEvent( elem, clone );

			if ( deepDataAndEvents ) {
				srcElements = getAll( elem );
				destElements = getAll( clone );

				for ( i = 0; srcElements[i]; ++i ) {
					cloneCopyEvent( srcElements[i], destElements[i] );
				}
			}
		}

		srcElements = destElements = null;

		// Return the cloned set
		return clone;
	},

	clean: function( elems, context, fragment, scripts ) {
		var i, j, elem, tag, wrap, depth, div, hasBody, tbody, len, handleScript, jsTags,
			safe = context === document && safeFragment,
			ret = [];

		// Ensure that context is a document
		if ( !context || typeof context.createDocumentFragment === "undefined" ) {
			context = document;
		}

		// Use the already-created safe fragment if context permits
		for ( i = 0; (elem = elems[i]) != null; i++ ) {
			if ( typeof elem === "number" ) {
				elem += "";
			}

			if ( !elem ) {
				continue;
			}

			// Convert html string into DOM nodes
			if ( typeof elem === "string" ) {
				if ( !rhtml.test( elem ) ) {
					elem = context.createTextNode( elem );
				} else {
					// Ensure a safe container in which to render the html
					safe = safe || createSafeFragment( context );
					div = context.createElement("div");
					safe.appendChild( div );

					// Fix "XHTML"-style tags in all browsers
					elem = elem.replace(rxhtmlTag, "<$1></$2>");

					// Go to html and back, then peel off extra wrappers
					tag = ( rtagName.exec( elem ) || ["", ""] )[1].toLowerCase();
					wrap = wrapMap[ tag ] || wrapMap._default;
					depth = wrap[0];
					div.innerHTML = wrap[1] + elem + wrap[2];

					// Move to the right depth
					while ( depth-- ) {
						div = div.lastChild;
					}

					// Remove IE's autoinserted <tbody> from table fragments
					if ( !jQuery.support.tbody ) {

						// String was a <table>, *may* have spurious <tbody>
						hasBody = rtbody.test(elem);
							tbody = tag === "table" && !hasBody ?
								div.firstChild && div.firstChild.childNodes :

								// String was a bare <thead> or <tfoot>
								wrap[1] === "<table>" && !hasBody ?
									div.childNodes :
									[];

						for ( j = tbody.length - 1; j >= 0 ; --j ) {
							if ( jQuery.nodeName( tbody[ j ], "tbody" ) && !tbody[ j ].childNodes.length ) {
								tbody[ j ].parentNode.removeChild( tbody[ j ] );
							}
						}
					}

					// IE completely kills leading whitespace when innerHTML is used
					if ( !jQuery.support.leadingWhitespace && rleadingWhitespace.test( elem ) ) {
						div.insertBefore( context.createTextNode( rleadingWhitespace.exec(elem)[0] ), div.firstChild );
					}

					elem = div.childNodes;

					// Take out of fragment container (we need a fresh div each time)
					div.parentNode.removeChild( div );
				}
			}

			if ( elem.nodeType ) {
				ret.push( elem );
			} else {
				jQuery.merge( ret, elem );
			}
		}

		// Fix #11356: Clear elements from safeFragment
		if ( div ) {
			elem = div = safe = null;
		}

		// Reset defaultChecked for any radios and checkboxes
		// about to be appended to the DOM in IE 6/7 (#8060)
		if ( !jQuery.support.appendChecked ) {
			for ( i = 0; (elem = ret[i]) != null; i++ ) {
				if ( jQuery.nodeName( elem, "input" ) ) {
					fixDefaultChecked( elem );
				} else if ( typeof elem.getElementsByTagName !== "undefined" ) {
					jQuery.grep( elem.getElementsByTagName("input"), fixDefaultChecked );
				}
			}
		}

		// Append elements to a provided document fragment
		if ( fragment ) {
			// Special handling of each script element
			handleScript = function( elem ) {
				// Check if we consider it executable
				if ( !elem.type || rscriptType.test( elem.type ) ) {
					// Detach the script and store it in the scripts array (if provided) or the fragment
					// Return truthy to indicate that it has been handled
					return scripts ?
						scripts.push( elem.parentNode ? elem.parentNode.removeChild( elem ) : elem ) :
						fragment.appendChild( elem );
				}
			};

			for ( i = 0; (elem = ret[i]) != null; i++ ) {
				// Check if we're done after handling an executable script
				if ( !( jQuery.nodeName( elem, "script" ) && handleScript( elem ) ) ) {
					// Append to fragment and handle embedded scripts
					fragment.appendChild( elem );
					if ( typeof elem.getElementsByTagName !== "undefined" ) {
						// handleScript alters the DOM, so use jQuery.merge to ensure snapshot iteration
						jsTags = jQuery.grep( jQuery.merge( [], elem.getElementsByTagName("script") ), handleScript );

						// Splice the scripts into ret after their former ancestor and advance our index beyond them
						ret.splice.apply( ret, [i + 1, 0].concat( jsTags ) );
						i += jsTags.length;
					}
				}
			}
		}

		return ret;
	},

	cleanData: function( elems, /* internal */ acceptData ) {
		var data, id, elem, type,
			i = 0,
			internalKey = jQuery.expando,
			cache = jQuery.cache,
			deleteExpando = jQuery.support.deleteExpando,
			special = jQuery.event.special;

		for ( ; (elem = elems[i]) != null; i++ ) {

			if ( acceptData || jQuery.acceptData( elem ) ) {

				id = elem[ internalKey ];
				data = id && cache[ id ];

				if ( data ) {
					if ( data.events ) {
						for ( type in data.events ) {
							if ( special[ type ] ) {
								jQuery.event.remove( elem, type );

							// This is a shortcut to avoid jQuery.event.remove's overhead
							} else {
								jQuery.removeEvent( elem, type, data.handle );
							}
						}
					}

					// Remove cache only if it was not already removed by jQuery.event.remove
					if ( cache[ id ] ) {

						delete cache[ id ];

						// IE does not allow us to delete expando properties from nodes,
						// nor does it have a removeAttribute function on Document nodes;
						// we must handle all of these cases
						if ( deleteExpando ) {
							delete elem[ internalKey ];

						} else if ( elem.removeAttribute ) {
							elem.removeAttribute( internalKey );

						} else {
							elem[ internalKey ] = null;
						}

						jQuery.deletedIds.push( id );
					}
				}
			}
		}
	}
});
// Limit scope pollution from any deprecated API
(function() {

var matched, browser;

// Use of jQuery.browser is frowned upon.
// More details: http://api.jquery.com/jQuery.browser
// jQuery.uaMatch maintained for back-compat
jQuery.uaMatch = function( ua ) {
	ua = ua.toLowerCase();

	var match = /(chrome)[ \/]([\w.]+)/.exec( ua ) ||
		/(webkit)[ \/]([\w.]+)/.exec( ua ) ||
		/(opera)(?:.*version|)[ \/]([\w.]+)/.exec( ua ) ||
		/(msie) ([\w.]+)/.exec( ua ) ||
		ua.indexOf("compatible") < 0 && /(mozilla)(?:.*? rv:([\w.]+)|)/.exec( ua ) ||
		[];

	return {
		browser: match[ 1 ] || "",
		version: match[ 2 ] || "0"
	};
};

matched = jQuery.uaMatch( navigator.userAgent );
browser = {};

if ( matched.browser ) {
	browser[ matched.browser ] = true;
	browser.version = matched.version;
}

// Chrome is Webkit, but Webkit is also Safari.
if ( browser.chrome ) {
	browser.webkit = true;
} else if ( browser.webkit ) {
	browser.safari = true;
}

jQuery.browser = browser;

jQuery.sub = function() {
	function jQuerySub( selector, context ) {
		return new jQuerySub.fn.init( selector, context );
	}
	jQuery.extend( true, jQuerySub, this );
	jQuerySub.superclass = this;
	jQuerySub.fn = jQuerySub.prototype = this();
	jQuerySub.fn.constructor = jQuerySub;
	jQuerySub.sub = this.sub;
	jQuerySub.fn.init = function init( selector, context ) {
		if ( context && context instanceof jQuery && !(context instanceof jQuerySub) ) {
			context = jQuerySub( context );
		}

		return jQuery.fn.init.call( this, selector, context, rootjQuerySub );
	};
	jQuerySub.fn.init.prototype = jQuerySub.fn;
	var rootjQuerySub = jQuerySub(document);
	return jQuerySub;
};

})();
var curCSS, iframe, iframeDoc,
	ralpha = /alpha\([^)]*\)/i,
	ropacity = /opacity=([^)]*)/,
	rposition = /^(top|right|bottom|left)$/,
	// swappable if display is none or starts with table except "table", "table-cell", or "table-caption"
	// see here for display values: https://developer.mozilla.org/en-US/docs/CSS/display
	rdisplayswap = /^(none|table(?!-c[ea]).+)/,
	rmargin = /^margin/,
	rnumsplit = new RegExp( "^(" + core_pnum + ")(.*)$", "i" ),
	rnumnonpx = new RegExp( "^(" + core_pnum + ")(?!px)[a-z%]+$", "i" ),
	rrelNum = new RegExp( "^([-+])=(" + core_pnum + ")", "i" ),
	elemdisplay = { BODY: "block" },

	cssShow = { position: "absolute", visibility: "hidden", display: "block" },
	cssNormalTransform = {
		letterSpacing: 0,
		fontWeight: 400
	},

	cssExpand = [ "Top", "Right", "Bottom", "Left" ],
	cssPrefixes = [ "Webkit", "O", "Moz", "ms" ],

	eventsToggle = jQuery.fn.toggle;

// return a css property mapped to a potentially vendor prefixed property
function vendorPropName( style, name ) {

	// shortcut for names that are not vendor prefixed
	if ( name in style ) {
		return name;
	}

	// check for vendor prefixed names
	var capName = name.charAt(0).toUpperCase() + name.slice(1),
		origName = name,
		i = cssPrefixes.length;

	while ( i-- ) {
		name = cssPrefixes[ i ] + capName;
		if ( name in style ) {
			return name;
		}
	}

	return origName;
}

function isHidden( elem, el ) {
	elem = el || elem;
	return jQuery.css( elem, "display" ) === "none" || !jQuery.contains( elem.ownerDocument, elem );
}

function showHide( elements, show ) {
	var elem, display,
		values = [],
		index = 0,
		length = elements.length;

	for ( ; index < length; index++ ) {
		elem = elements[ index ];
		if ( !elem.style ) {
			continue;
		}
		values[ index ] = jQuery._data( elem, "olddisplay" );
		if ( show ) {
			// Reset the inline display of this element to learn if it is
			// being hidden by cascaded rules or not
			if ( !values[ index ] && elem.style.display === "none" ) {
				elem.style.display = "";
			}

			// Set elements which have been overridden with display: none
			// in a stylesheet to whatever the default browser style is
			// for such an element
			if ( elem.style.display === "" && isHidden( elem ) ) {
				values[ index ] = jQuery._data( elem, "olddisplay", css_defaultDisplay(elem.nodeName) );
			}
		} else {
			display = curCSS( elem, "display" );

			if ( !values[ index ] && display !== "none" ) {
				jQuery._data( elem, "olddisplay", display );
			}
		}
	}

	// Set the display of most of the elements in a second loop
	// to avoid the constant reflow
	for ( index = 0; index < length; index++ ) {
		elem = elements[ index ];
		if ( !elem.style ) {
			continue;
		}
		if ( !show || elem.style.display === "none" || elem.style.display === "" ) {
			elem.style.display = show ? values[ index ] || "" : "none";
		}
	}

	return elements;
}

jQuery.fn.extend({
	css: function( name, value ) {
		return jQuery.access( this, function( elem, name, value ) {
			return value !== undefined ?
				jQuery.style( elem, name, value ) :
				jQuery.css( elem, name );
		}, name, value, arguments.length > 1 );
	},
	show: function() {
		return showHide( this, true );
	},
	hide: function() {
		return showHide( this );
	},
	toggle: function( state, fn2 ) {
		var bool = typeof state === "boolean";

		if ( jQuery.isFunction( state ) && jQuery.isFunction( fn2 ) ) {
			return eventsToggle.apply( this, arguments );
		}

		return this.each(function() {
			if ( bool ? state : isHidden( this ) ) {
				jQuery( this ).show();
			} else {
				jQuery( this ).hide();
			}
		});
	}
});

jQuery.extend({
	// Add in style property hooks for overriding the default
	// behavior of getting and setting a style property
	cssHooks: {
		opacity: {
			get: function( elem, computed ) {
				if ( computed ) {
					// We should always get a number back from opacity
					var ret = curCSS( elem, "opacity" );
					return ret === "" ? "1" : ret;

				}
			}
		}
	},

	// Exclude the following css properties to add px
	cssNumber: {
		"fillOpacity": true,
		"fontWeight": true,
		"lineHeight": true,
		"opacity": true,
		"orphans": true,
		"widows": true,
		"zIndex": true,
		"zoom": true
	},

	// Add in properties whose names you wish to fix before
	// setting or getting the value
	cssProps: {
		// normalize float css property
		"float": jQuery.support.cssFloat ? "cssFloat" : "styleFloat"
	},

	// Get and set the style property on a DOM Node
	style: function( elem, name, value, extra ) {
		// Don't set styles on text and comment nodes
		if ( !elem || elem.nodeType === 3 || elem.nodeType === 8 || !elem.style ) {
			return;
		}

		// Make sure that we're working with the right name
		var ret, type, hooks,
			origName = jQuery.camelCase( name ),
			style = elem.style;

		name = jQuery.cssProps[ origName ] || ( jQuery.cssProps[ origName ] = vendorPropName( style, origName ) );

		// gets hook for the prefixed version
		// followed by the unprefixed version
		hooks = jQuery.cssHooks[ name ] || jQuery.cssHooks[ origName ];

		// Check if we're setting a value
		if ( value !== undefined ) {
			type = typeof value;

			// convert relative number strings (+= or -=) to relative numbers. #7345
			if ( type === "string" && (ret = rrelNum.exec( value )) ) {
				value = ( ret[1] + 1 ) * ret[2] + parseFloat( jQuery.css( elem, name ) );
				// Fixes bug #9237
				type = "number";
			}

			// Make sure that NaN and null values aren't set. See: #7116
			if ( value == null || type === "number" && isNaN( value ) ) {
				return;
			}

			// If a number was passed in, add 'px' to the (except for certain CSS properties)
			if ( type === "number" && !jQuery.cssNumber[ origName ] ) {
				value += "px";
			}

			// If a hook was provided, use that value, otherwise just set the specified value
			if ( !hooks || !("set" in hooks) || (value = hooks.set( elem, value, extra )) !== undefined ) {
				// Wrapped to prevent IE from throwing errors when 'invalid' values are provided
				// Fixes bug #5509
				try {
					style[ name ] = value;
				} catch(e) {}
			}

		} else {
			// If a hook was provided get the non-computed value from there
			if ( hooks && "get" in hooks && (ret = hooks.get( elem, false, extra )) !== undefined ) {
				return ret;
			}

			// Otherwise just get the value from the style object
			return style[ name ];
		}
	},

	css: function( elem, name, numeric, extra ) {
		var val, num, hooks,
			origName = jQuery.camelCase( name );

		// Make sure that we're working with the right name
		name = jQuery.cssProps[ origName ] || ( jQuery.cssProps[ origName ] = vendorPropName( elem.style, origName ) );

		// gets hook for the prefixed version
		// followed by the unprefixed version
		hooks = jQuery.cssHooks[ name ] || jQuery.cssHooks[ origName ];

		// If a hook was provided get the computed value from there
		if ( hooks && "get" in hooks ) {
			val = hooks.get( elem, true, extra );
		}

		// Otherwise, if a way to get the computed value exists, use that
		if ( val === undefined ) {
			val = curCSS( elem, name );
		}

		//convert "normal" to computed value
		if ( val === "normal" && name in cssNormalTransform ) {
			val = cssNormalTransform[ name ];
		}

		// Return, converting to number if forced or a qualifier was provided and val looks numeric
		if ( numeric || extra !== undefined ) {
			num = parseFloat( val );
			return numeric || jQuery.isNumeric( num ) ? num || 0 : val;
		}
		return val;
	},

	// A method for quickly swapping in/out CSS properties to get correct calculations
	swap: function( elem, options, callback ) {
		var ret, name,
			old = {};

		// Remember the old values, and insert the new ones
		for ( name in options ) {
			old[ name ] = elem.style[ name ];
			elem.style[ name ] = options[ name ];
		}

		ret = callback.call( elem );

		// Revert the old values
		for ( name in options ) {
			elem.style[ name ] = old[ name ];
		}

		return ret;
	}
});

// NOTE: To any future maintainer, we've window.getComputedStyle
// because jsdom on node.js will break without it.
if ( window.getComputedStyle ) {
	curCSS = function( elem, name ) {
		var ret, width, minWidth, maxWidth,
			computed = window.getComputedStyle( elem, null ),
			style = elem.style;

		if ( computed ) {

			// getPropertyValue is only needed for .css('filter') in IE9, see #12537
			ret = computed.getPropertyValue( name ) || computed[ name ];

			if ( ret === "" && !jQuery.contains( elem.ownerDocument, elem ) ) {
				ret = jQuery.style( elem, name );
			}

			// A tribute to the "awesome hack by Dean Edwards"
			// Chrome < 17 and Safari 5.0 uses "computed value" instead of "used value" for margin-right
			// Safari 5.1.7 (at least) returns percentage for a larger set of values, but width seems to be reliably pixels
			// this is against the CSSOM draft spec: http://dev.w3.org/csswg/cssom/#resolved-values
			if ( rnumnonpx.test( ret ) && rmargin.test( name ) ) {
				width = style.width;
				minWidth = style.minWidth;
				maxWidth = style.maxWidth;

				style.minWidth = style.maxWidth = style.width = ret;
				ret = computed.width;

				style.width = width;
				style.minWidth = minWidth;
				style.maxWidth = maxWidth;
			}
		}

		return ret;
	};
} else if ( document.documentElement.currentStyle ) {
	curCSS = function( elem, name ) {
		var left, rsLeft,
			ret = elem.currentStyle && elem.currentStyle[ name ],
			style = elem.style;

		// Avoid setting ret to empty string here
		// so we don't default to auto
		if ( ret == null && style && style[ name ] ) {
			ret = style[ name ];
		}

		// From the awesome hack by Dean Edwards
		// http://erik.eae.net/archives/2007/07/27/18.54.15/#comment-102291

		// If we're not dealing with a regular pixel number
		// but a number that has a weird ending, we need to convert it to pixels
		// but not position css attributes, as those are proportional to the parent element instead
		// and we can't measure the parent instead because it might trigger a "stacking dolls" problem
		if ( rnumnonpx.test( ret ) && !rposition.test( name ) ) {

			// Remember the original values
			left = style.left;
			rsLeft = elem.runtimeStyle && elem.runtimeStyle.left;

			// Put in the new values to get a computed value out
			if ( rsLeft ) {
				elem.runtimeStyle.left = elem.currentStyle.left;
			}
			style.left = name === "fontSize" ? "1em" : ret;
			ret = style.pixelLeft + "px";

			// Revert the changed values
			style.left = left;
			if ( rsLeft ) {
				elem.runtimeStyle.left = rsLeft;
			}
		}

		return ret === "" ? "auto" : ret;
	};
}

function setPositiveNumber( elem, value, subtract ) {
	var matches = rnumsplit.exec( value );
	return matches ?
			Math.max( 0, matches[ 1 ] - ( subtract || 0 ) ) + ( matches[ 2 ] || "px" ) :
			value;
}

function augmentWidthOrHeight( elem, name, extra, isBorderBox ) {
	var i = extra === ( isBorderBox ? "border" : "content" ) ?
		// If we already have the right measurement, avoid augmentation
		4 :
		// Otherwise initialize for horizontal or vertical properties
		name === "width" ? 1 : 0,

		val = 0;

	for ( ; i < 4; i += 2 ) {
		// both box models exclude margin, so add it if we want it
		if ( extra === "margin" ) {
			// we use jQuery.css instead of curCSS here
			// because of the reliableMarginRight CSS hook!
			val += jQuery.css( elem, extra + cssExpand[ i ], true );
		}

		// From this point on we use curCSS for maximum performance (relevant in animations)
		if ( isBorderBox ) {
			// border-box includes padding, so remove it if we want content
			if ( extra === "content" ) {
				val -= parseFloat( curCSS( elem, "padding" + cssExpand[ i ] ) ) || 0;
			}

			// at this point, extra isn't border nor margin, so remove border
			if ( extra !== "margin" ) {
				val -= parseFloat( curCSS( elem, "border" + cssExpand[ i ] + "Width" ) ) || 0;
			}
		} else {
			// at this point, extra isn't content, so add padding
			val += parseFloat( curCSS( elem, "padding" + cssExpand[ i ] ) ) || 0;

			// at this point, extra isn't content nor padding, so add border
			if ( extra !== "padding" ) {
				val += parseFloat( curCSS( elem, "border" + cssExpand[ i ] + "Width" ) ) || 0;
			}
		}
	}

	return val;
}

function getWidthOrHeight( elem, name, extra ) {

	// Start with offset property, which is equivalent to the border-box value
	var val = name === "width" ? elem.offsetWidth : elem.offsetHeight,
		valueIsBorderBox = true,
		isBorderBox = jQuery.support.boxSizing && jQuery.css( elem, "boxSizing" ) === "border-box";

	// some non-html elements return undefined for offsetWidth, so check for null/undefined
	// svg - https://bugzilla.mozilla.org/show_bug.cgi?id=649285
	// MathML - https://bugzilla.mozilla.org/show_bug.cgi?id=491668
	if ( val <= 0 || val == null ) {
		// Fall back to computed then uncomputed css if necessary
		val = curCSS( elem, name );
		if ( val < 0 || val == null ) {
			val = elem.style[ name ];
		}

		// Computed unit is not pixels. Stop here and return.
		if ( rnumnonpx.test(val) ) {
			return val;
		}

		// we need the check for style in case a browser which returns unreliable values
		// for getComputedStyle silently falls back to the reliable elem.style
		valueIsBorderBox = isBorderBox && ( jQuery.support.boxSizingReliable || val === elem.style[ name ] );

		// Normalize "", auto, and prepare for extra
		val = parseFloat( val ) || 0;
	}

	// use the active box-sizing model to add/subtract irrelevant styles
	return ( val +
		augmentWidthOrHeight(
			elem,
			name,
			extra || ( isBorderBox ? "border" : "content" ),
			valueIsBorderBox
		)
	) + "px";
}


// Try to determine the default display value of an element
function css_defaultDisplay( nodeName ) {
	if ( elemdisplay[ nodeName ] ) {
		return elemdisplay[ nodeName ];
	}

	var elem = jQuery( "<" + nodeName + ">" ).appendTo( document.body ),
		display = elem.css("display");
	elem.remove();

	// If the simple way fails,
	// get element's real default display by attaching it to a temp iframe
	if ( display === "none" || display === "" ) {
		// Use the already-created iframe if possible
		iframe = document.body.appendChild(
			iframe || jQuery.extend( document.createElement("iframe"), {
				frameBorder: 0,
				width: 0,
				height: 0
			})
		);

		// Create a cacheable copy of the iframe document on first call.
		// IE and Opera will allow us to reuse the iframeDoc without re-writing the fake HTML
		// document to it; WebKit & Firefox won't allow reusing the iframe document.
		if ( !iframeDoc || !iframe.createElement ) {
			iframeDoc = ( iframe.contentWindow || iframe.contentDocument ).document;
			iframeDoc.write("<!doctype html><html><body>");
			iframeDoc.close();
		}

		elem = iframeDoc.body.appendChild( iframeDoc.createElement(nodeName) );

		display = curCSS( elem, "display" );
		document.body.removeChild( iframe );
	}

	// Store the correct default display
	elemdisplay[ nodeName ] = display;

	return display;
}

jQuery.each([ "height", "width" ], function( i, name ) {
	jQuery.cssHooks[ name ] = {
		get: function( elem, computed, extra ) {
			if ( computed ) {
				// certain elements can have dimension info if we invisibly show them
				// however, it must have a current display style that would benefit from this
				if ( elem.offsetWidth === 0 && rdisplayswap.test( curCSS( elem, "display" ) ) ) {
					return jQuery.swap( elem, cssShow, function() {
						return getWidthOrHeight( elem, name, extra );
					});
				} else {
					return getWidthOrHeight( elem, name, extra );
				}
			}
		},

		set: function( elem, value, extra ) {
			return setPositiveNumber( elem, value, extra ?
				augmentWidthOrHeight(
					elem,
					name,
					extra,
					jQuery.support.boxSizing && jQuery.css( elem, "boxSizing" ) === "border-box"
				) : 0
			);
		}
	};
});

if ( !jQuery.support.opacity ) {
	jQuery.cssHooks.opacity = {
		get: function( elem, computed ) {
			// IE uses filters for opacity
			return ropacity.test( (computed && elem.currentStyle ? elem.currentStyle.filter : elem.style.filter) || "" ) ?
				( 0.01 * parseFloat( RegExp.$1 ) ) + "" :
				computed ? "1" : "";
		},

		set: function( elem, value ) {
			var style = elem.style,
				currentStyle = elem.currentStyle,
				opacity = jQuery.isNumeric( value ) ? "alpha(opacity=" + value * 100 + ")" : "",
				filter = currentStyle && currentStyle.filter || style.filter || "";

			// IE has trouble with opacity if it does not have layout
			// Force it by setting the zoom level
			style.zoom = 1;

			// if setting opacity to 1, and no other filters exist - attempt to remove filter attribute #6652
			if ( value >= 1 && jQuery.trim( filter.replace( ralpha, "" ) ) === "" &&
				style.removeAttribute ) {

				// Setting style.filter to null, "" & " " still leave "filter:" in the cssText
				// if "filter:" is present at all, clearType is disabled, we want to avoid this
				// style.removeAttribute is IE Only, but so apparently is this code path...
				style.removeAttribute( "filter" );

				// if there there is no filter style applied in a css rule, we are done
				if ( currentStyle && !currentStyle.filter ) {
					return;
				}
			}

			// otherwise, set new filter values
			style.filter = ralpha.test( filter ) ?
				filter.replace( ralpha, opacity ) :
				filter + " " + opacity;
		}
	};
}

// These hooks cannot be added until DOM ready because the support test
// for it is not run until after DOM ready
jQuery(function() {
	if ( !jQuery.support.reliableMarginRight ) {
		jQuery.cssHooks.marginRight = {
			get: function( elem, computed ) {
				// WebKit Bug 13343 - getComputedStyle returns wrong value for margin-right
				// Work around by temporarily setting element display to inline-block
				return jQuery.swap( elem, { "display": "inline-block" }, function() {
					if ( computed ) {
						return curCSS( elem, "marginRight" );
					}
				});
			}
		};
	}

	// Webkit bug: https://bugs.webkit.org/show_bug.cgi?id=29084
	// getComputedStyle returns percent when specified for top/left/bottom/right
	// rather than make the css module depend on the offset module, we just check for it here
	if ( !jQuery.support.pixelPosition && jQuery.fn.position ) {
		jQuery.each( [ "top", "left" ], function( i, prop ) {
			jQuery.cssHooks[ prop ] = {
				get: function( elem, computed ) {
					if ( computed ) {
						var ret = curCSS( elem, prop );
						// if curCSS returns percentage, fallback to offset
						return rnumnonpx.test( ret ) ? jQuery( elem ).position()[ prop ] + "px" : ret;
					}
				}
			};
		});
	}

});

if ( jQuery.expr && jQuery.expr.filters ) {
	jQuery.expr.filters.hidden = function( elem ) {
		return ( elem.offsetWidth === 0 && elem.offsetHeight === 0 ) || (!jQuery.support.reliableHiddenOffsets && ((elem.style && elem.style.display) || curCSS( elem, "display" )) === "none");
	};

	jQuery.expr.filters.visible = function( elem ) {
		return !jQuery.expr.filters.hidden( elem );
	};
}

// These hooks are used by animate to expand properties
jQuery.each({
	margin: "",
	padding: "",
	border: "Width"
}, function( prefix, suffix ) {
	jQuery.cssHooks[ prefix + suffix ] = {
		expand: function( value ) {
			var i,

				// assumes a single number if not a string
				parts = typeof value === "string" ? value.split(" ") : [ value ],
				expanded = {};

			for ( i = 0; i < 4; i++ ) {
				expanded[ prefix + cssExpand[ i ] + suffix ] =
					parts[ i ] || parts[ i - 2 ] || parts[ 0 ];
			}

			return expanded;
		}
	};

	if ( !rmargin.test( prefix ) ) {
		jQuery.cssHooks[ prefix + suffix ].set = setPositiveNumber;
	}
});
var r20 = /%20/g,
	rbracket = /\[\]$/,
	rCRLF = /\r?\n/g,
	rinput = /^(?:color|date|datetime|datetime-local|email|hidden|month|number|password|range|search|tel|text|time|url|week)$/i,
	rselectTextarea = /^(?:select|textarea)/i;

jQuery.fn.extend({
	serialize: function() {
		return jQuery.param( this.serializeArray() );
	},
	serializeArray: function() {
		return this.map(function(){
			return this.elements ? jQuery.makeArray( this.elements ) : this;
		})
		.filter(function(){
			return this.name && !this.disabled &&
				( this.checked || rselectTextarea.test( this.nodeName ) ||
					rinput.test( this.type ) );
		})
		.map(function( i, elem ){
			var val = jQuery( this ).val();

			return val == null ?
				null :
				jQuery.isArray( val ) ?
					jQuery.map( val, function( val, i ){
						return { name: elem.name, value: val.replace( rCRLF, "\r\n" ) };
					}) :
					{ name: elem.name, value: val.replace( rCRLF, "\r\n" ) };
		}).get();
	}
});

//Serialize an array of form elements or a set of
//key/values into a query string
jQuery.param = function( a, traditional ) {
	var prefix,
		s = [],
		add = function( key, value ) {
			// If value is a function, invoke it and return its value
			value = jQuery.isFunction( value ) ? value() : ( value == null ? "" : value );
			s[ s.length ] = encodeURIComponent( key ) + "=" + encodeURIComponent( value );
		};

	// Set traditional to true for jQuery <= 1.3.2 behavior.
	if ( traditional === undefined ) {
		traditional = jQuery.ajaxSettings && jQuery.ajaxSettings.traditional;
	}

	// If an array was passed in, assume that it is an array of form elements.
	if ( jQuery.isArray( a ) || ( a.jquery && !jQuery.isPlainObject( a ) ) ) {
		// Serialize the form elements
		jQuery.each( a, function() {
			add( this.name, this.value );
		});

	} else {
		// If traditional, encode the "old" way (the way 1.3.2 or older
		// did it), otherwise encode params recursively.
		for ( prefix in a ) {
			buildParams( prefix, a[ prefix ], traditional, add );
		}
	}

	// Return the resulting serialization
	return s.join( "&" ).replace( r20, "+" );
};

function buildParams( prefix, obj, traditional, add ) {
	var name;

	if ( jQuery.isArray( obj ) ) {
		// Serialize array item.
		jQuery.each( obj, function( i, v ) {
			if ( traditional || rbracket.test( prefix ) ) {
				// Treat each array item as a scalar.
				add( prefix, v );

			} else {
				// If array item is non-scalar (array or object), encode its
				// numeric index to resolve deserialization ambiguity issues.
				// Note that rack (as of 1.0.0) can't currently deserialize
				// nested arrays properly, and attempting to do so may cause
				// a server error. Possible fixes are to modify rack's
				// deserialization algorithm or to provide an option or flag
				// to force array serialization to be shallow.
				buildParams( prefix + "[" + ( typeof v === "object" ? i : "" ) + "]", v, traditional, add );
			}
		});

	} else if ( !traditional && jQuery.type( obj ) === "object" ) {
		// Serialize object item.
		for ( name in obj ) {
			buildParams( prefix + "[" + name + "]", obj[ name ], traditional, add );
		}

	} else {
		// Serialize scalar item.
		add( prefix, obj );
	}
}
var
	// Document location
	ajaxLocParts,
	ajaxLocation,

	rhash = /#.*$/,
	rheaders = /^(.*?):[ \t]*([^\r\n]*)\r?$/mg, // IE leaves an \r character at EOL
	// #7653, #8125, #8152: local protocol detection
	rlocalProtocol = /^(?:about|app|app\-storage|.+\-extension|file|res|widget):$/,
	rnoContent = /^(?:GET|HEAD)$/,
	rprotocol = /^\/\//,
	rquery = /\?/,
	rscript = /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
	rts = /([?&])_=[^&]*/,
	rurl = /^([\w\+\.\-]+:)(?:\/\/([^\/?#:]*)(?::(\d+)|)|)/,

	// Keep a copy of the old load method
	_load = jQuery.fn.load,

	/* Prefilters
	 * 1) They are useful to introduce custom dataTypes (see ajax/jsonp.js for an example)
	 * 2) These are called:
	 *    - BEFORE asking for a transport
	 *    - AFTER param serialization (s.data is a string if s.processData is true)
	 * 3) key is the dataType
	 * 4) the catchall symbol "*" can be used
	 * 5) execution will start with transport dataType and THEN continue down to "*" if needed
	 */
	prefilters = {},

	/* Transports bindings
	 * 1) key is the dataType
	 * 2) the catchall symbol "*" can be used
	 * 3) selection will start with transport dataType and THEN go to "*" if needed
	 */
	transports = {},

	// Avoid comment-prolog char sequence (#10098); must appease lint and evade compression
	allTypes = ["*/"] + ["*"];

// #8138, IE may throw an exception when accessing
// a field from window.location if document.domain has been set
try {
	ajaxLocation = location.href;
} catch( e ) {
	// Use the href attribute of an A element
	// since IE will modify it given document.location
	ajaxLocation = document.createElement( "a" );
	ajaxLocation.href = "";
	ajaxLocation = ajaxLocation.href;
}

// Segment location into parts
ajaxLocParts = rurl.exec( ajaxLocation.toLowerCase() ) || [];

// Base "constructor" for jQuery.ajaxPrefilter and jQuery.ajaxTransport
function addToPrefiltersOrTransports( structure ) {

	// dataTypeExpression is optional and defaults to "*"
	return function( dataTypeExpression, func ) {

		if ( typeof dataTypeExpression !== "string" ) {
			func = dataTypeExpression;
			dataTypeExpression = "*";
		}

		var dataType, list, placeBefore,
			dataTypes = dataTypeExpression.toLowerCase().split( core_rspace ),
			i = 0,
			length = dataTypes.length;

		if ( jQuery.isFunction( func ) ) {
			// For each dataType in the dataTypeExpression
			for ( ; i < length; i++ ) {
				dataType = dataTypes[ i ];
				// We control if we're asked to add before
				// any existing element
				placeBefore = /^\+/.test( dataType );
				if ( placeBefore ) {
					dataType = dataType.substr( 1 ) || "*";
				}
				list = structure[ dataType ] = structure[ dataType ] || [];
				// then we add to the structure accordingly
				list[ placeBefore ? "unshift" : "push" ]( func );
			}
		}
	};
}

// Base inspection function for prefilters and transports
function inspectPrefiltersOrTransports( structure, options, originalOptions, jqXHR,
		dataType /* internal */, inspected /* internal */ ) {

	dataType = dataType || options.dataTypes[ 0 ];
	inspected = inspected || {};

	inspected[ dataType ] = true;

	var selection,
		list = structure[ dataType ],
		i = 0,
		length = list ? list.length : 0,
		executeOnly = ( structure === prefilters );

	for ( ; i < length && ( executeOnly || !selection ); i++ ) {
		selection = list[ i ]( options, originalOptions, jqXHR );
		// If we got redirected to another dataType
		// we try there if executing only and not done already
		if ( typeof selection === "string" ) {
			if ( !executeOnly || inspected[ selection ] ) {
				selection = undefined;
			} else {
				options.dataTypes.unshift( selection );
				selection = inspectPrefiltersOrTransports(
						structure, options, originalOptions, jqXHR, selection, inspected );
			}
		}
	}
	// If we're only executing or nothing was selected
	// we try the catchall dataType if not done already
	if ( ( executeOnly || !selection ) && !inspected[ "*" ] ) {
		selection = inspectPrefiltersOrTransports(
				structure, options, originalOptions, jqXHR, "*", inspected );
	}
	// unnecessary when only executing (prefilters)
	// but it'll be ignored by the caller in that case
	return selection;
}

// A special extend for ajax options
// that takes "flat" options (not to be deep extended)
// Fixes #9887
function ajaxExtend( target, src ) {
	var key, deep,
		flatOptions = jQuery.ajaxSettings.flatOptions || {};
	for ( key in src ) {
		if ( src[ key ] !== undefined ) {
			( flatOptions[ key ] ? target : ( deep || ( deep = {} ) ) )[ key ] = src[ key ];
		}
	}
	if ( deep ) {
		jQuery.extend( true, target, deep );
	}
}

jQuery.fn.load = function( url, params, callback ) {
	if ( typeof url !== "string" && _load ) {
		return _load.apply( this, arguments );
	}

	// Don't do a request if no elements are being requested
	if ( !this.length ) {
		return this;
	}

	var selector, type, response,
		self = this,
		off = url.indexOf(" ");

	if ( off >= 0 ) {
		selector = url.slice( off, url.length );
		url = url.slice( 0, off );
	}

	// If it's a function
	if ( jQuery.isFunction( params ) ) {

		// We assume that it's the callback
		callback = params;
		params = undefined;

	// Otherwise, build a param string
	} else if ( params && typeof params === "object" ) {
		type = "POST";
	}

	// Request the remote document
	jQuery.ajax({
		url: url,

		// if "type" variable is undefined, then "GET" method will be used
		type: type,
		dataType: "html",
		data: params,
		complete: function( jqXHR, status ) {
			if ( callback ) {
				self.each( callback, response || [ jqXHR.responseText, status, jqXHR ] );
			}
		}
	}).done(function( responseText ) {

		// Save response for use in complete callback
		response = arguments;

		// See if a selector was specified
		self.html( selector ?

			// Create a dummy div to hold the results
			jQuery("<div>")

				// inject the contents of the document in, removing the scripts
				// to avoid any 'Permission Denied' errors in IE
				.append( responseText.replace( rscript, "" ) )

				// Locate the specified elements
				.find( selector ) :

			// If not, just inject the full result
			responseText );

	});

	return this;
};

// Attach a bunch of functions for handling common AJAX events
jQuery.each( "ajaxStart ajaxStop ajaxComplete ajaxError ajaxSuccess ajaxSend".split( " " ), function( i, o ){
	jQuery.fn[ o ] = function( f ){
		return this.on( o, f );
	};
});

jQuery.each( [ "get", "post" ], function( i, method ) {
	jQuery[ method ] = function( url, data, callback, type ) {
		// shift arguments if data argument was omitted
		if ( jQuery.isFunction( data ) ) {
			type = type || callback;
			callback = data;
			data = undefined;
		}

		return jQuery.ajax({
			type: method,
			url: url,
			data: data,
			success: callback,
			dataType: type
		});
	};
});

jQuery.extend({

	getScript: function( url, callback ) {
		return jQuery.get( url, undefined, callback, "script" );
	},

	getJSON: function( url, data, callback ) {
		return jQuery.get( url, data, callback, "json" );
	},

	// Creates a full fledged settings object into target
	// with both ajaxSettings and settings fields.
	// If target is omitted, writes into ajaxSettings.
	ajaxSetup: function( target, settings ) {
		if ( settings ) {
			// Building a settings object
			ajaxExtend( target, jQuery.ajaxSettings );
		} else {
			// Extending ajaxSettings
			settings = target;
			target = jQuery.ajaxSettings;
		}
		ajaxExtend( target, settings );
		return target;
	},

	ajaxSettings: {
		url: ajaxLocation,
		isLocal: rlocalProtocol.test( ajaxLocParts[ 1 ] ),
		global: true,
		type: "GET",
		contentType: "application/x-www-form-urlencoded; charset=UTF-8",
		processData: true,
		async: true,
		/*
		timeout: 0,
		data: null,
		dataType: null,
		username: null,
		password: null,
		cache: null,
		throws: false,
		traditional: false,
		headers: {},
		*/

		accepts: {
			xml: "application/xml, text/xml",
			html: "text/html",
			text: "text/plain",
			json: "application/json, text/javascript",
			"*": allTypes
		},

		contents: {
			xml: /xml/,
			html: /html/,
			json: /json/
		},

		responseFields: {
			xml: "responseXML",
			text: "responseText"
		},

		// List of data converters
		// 1) key format is "source_type destination_type" (a single space in-between)
		// 2) the catchall symbol "*" can be used for source_type
		converters: {

			// Convert anything to text
			"* text": window.String,

			// Text to html (true = no transformation)
			"text html": true,

			// Evaluate text as a json expression
			"text json": jQuery.parseJSON,

			// Parse text as xml
			"text xml": jQuery.parseXML
		},

		// For options that shouldn't be deep extended:
		// you can add your own custom options here if
		// and when you create one that shouldn't be
		// deep extended (see ajaxExtend)
		flatOptions: {
			context: true,
			url: true
		}
	},

	ajaxPrefilter: addToPrefiltersOrTransports( prefilters ),
	ajaxTransport: addToPrefiltersOrTransports( transports ),

	// Main method
	ajax: function( url, options ) {

		// If url is an object, simulate pre-1.5 signature
		if ( typeof url === "object" ) {
			options = url;
			url = undefined;
		}

		// Force options to be an object
		options = options || {};

		var // ifModified key
			ifModifiedKey,
			// Response headers
			responseHeadersString,
			responseHeaders,
			// transport
			transport,
			// timeout handle
			timeoutTimer,
			// Cross-domain detection vars
			parts,
			// To know if global events are to be dispatched
			fireGlobals,
			// Loop variable
			i,
			// Create the final options object
			s = jQuery.ajaxSetup( {}, options ),
			// Callbacks context
			callbackContext = s.context || s,
			// Context for global events
			// It's the callbackContext if one was provided in the options
			// and if it's a DOM node or a jQuery collection
			globalEventContext = callbackContext !== s &&
				( callbackContext.nodeType || callbackContext instanceof jQuery ) ?
						jQuery( callbackContext ) : jQuery.event,
			// Deferreds
			deferred = jQuery.Deferred(),
			completeDeferred = jQuery.Callbacks( "once memory" ),
			// Status-dependent callbacks
			statusCode = s.statusCode || {},
			// Headers (they are sent all at once)
			requestHeaders = {},
			requestHeadersNames = {},
			// The jqXHR state
			state = 0,
			// Default abort message
			strAbort = "canceled",
			// Fake xhr
			jqXHR = {

				readyState: 0,

				// Caches the header
				setRequestHeader: function( name, value ) {
					if ( !state ) {
						var lname = name.toLowerCase();
						name = requestHeadersNames[ lname ] = requestHeadersNames[ lname ] || name;
						requestHeaders[ name ] = value;
					}
					return this;
				},

				// Raw string
				getAllResponseHeaders: function() {
					return state === 2 ? responseHeadersString : null;
				},

				// Builds headers hashtable if needed
				getResponseHeader: function( key ) {
					var match;
					if ( state === 2 ) {
						if ( !responseHeaders ) {
							responseHeaders = {};
							while( ( match = rheaders.exec( responseHeadersString ) ) ) {
								responseHeaders[ match[1].toLowerCase() ] = match[ 2 ];
							}
						}
						match = responseHeaders[ key.toLowerCase() ];
					}
					return match === undefined ? null : match;
				},

				// Overrides response content-type header
				overrideMimeType: function( type ) {
					if ( !state ) {
						s.mimeType = type;
					}
					return this;
				},

				// Cancel the request
				abort: function( statusText ) {
					statusText = statusText || strAbort;
					if ( transport ) {
						transport.abort( statusText );
					}
					done( 0, statusText );
					return this;
				}
			};

		// Callback for when everything is done
		// It is defined here because jslint complains if it is declared
		// at the end of the function (which would be more logical and readable)
		function done( status, nativeStatusText, responses, headers ) {
			var isSuccess, success, error, response, modified,
				statusText = nativeStatusText;

			// Called once
			if ( state === 2 ) {
				return;
			}

			// State is "done" now
			state = 2;

			// Clear timeout if it exists
			if ( timeoutTimer ) {
				clearTimeout( timeoutTimer );
			}

			// Dereference transport for early garbage collection
			// (no matter how long the jqXHR object will be used)
			transport = undefined;

			// Cache response headers
			responseHeadersString = headers || "";

			// Set readyState
			jqXHR.readyState = status > 0 ? 4 : 0;

			// Get response data
			if ( responses ) {
				response = ajaxHandleResponses( s, jqXHR, responses );
			}

			// If successful, handle type chaining
			if ( status >= 200 && status < 300 || status === 304 ) {

				// Set the If-Modified-Since and/or If-None-Match header, if in ifModified mode.
				if ( s.ifModified ) {

					modified = jqXHR.getResponseHeader("Last-Modified");
					if ( modified ) {
						jQuery.lastModified[ ifModifiedKey ] = modified;
					}
					modified = jqXHR.getResponseHeader("Etag");
					if ( modified ) {
						jQuery.etag[ ifModifiedKey ] = modified;
					}
				}

				// If not modified
				if ( status === 304 ) {

					statusText = "notmodified";
					isSuccess = true;

				// If we have data
				} else {

					isSuccess = ajaxConvert( s, response );
					statusText = isSuccess.state;
					success = isSuccess.data;
					error = isSuccess.error;
					isSuccess = !error;
				}
			} else {
				// We extract error from statusText
				// then normalize statusText and status for non-aborts
				error = statusText;
				if ( !statusText || status ) {
					statusText = "error";
					if ( status < 0 ) {
						status = 0;
					}
				}
			}

			// Set data for the fake xhr object
			jqXHR.status = status;
			jqXHR.statusText = ( nativeStatusText || statusText ) + "";

			// Success/Error
			if ( isSuccess ) {
				deferred.resolveWith( callbackContext, [ success, statusText, jqXHR ] );
			} else {
				deferred.rejectWith( callbackContext, [ jqXHR, statusText, error ] );
			}

			// Status-dependent callbacks
			jqXHR.statusCode( statusCode );
			statusCode = undefined;

			if ( fireGlobals ) {
				globalEventContext.trigger( "ajax" + ( isSuccess ? "Success" : "Error" ),
						[ jqXHR, s, isSuccess ? success : error ] );
			}

			// Complete
			completeDeferred.fireWith( callbackContext, [ jqXHR, statusText ] );

			if ( fireGlobals ) {
				globalEventContext.trigger( "ajaxComplete", [ jqXHR, s ] );
				// Handle the global AJAX counter
				if ( !( --jQuery.active ) ) {
					jQuery.event.trigger( "ajaxStop" );
				}
			}
		}

		// Attach deferreds
		deferred.promise( jqXHR );
		jqXHR.success = jqXHR.done;
		jqXHR.error = jqXHR.fail;
		jqXHR.complete = completeDeferred.add;

		// Status-dependent callbacks
		jqXHR.statusCode = function( map ) {
			if ( map ) {
				var tmp;
				if ( state < 2 ) {
					for ( tmp in map ) {
						statusCode[ tmp ] = [ statusCode[tmp], map[tmp] ];
					}
				} else {
					tmp = map[ jqXHR.status ];
					jqXHR.always( tmp );
				}
			}
			return this;
		};

		// Remove hash character (#7531: and string promotion)
		// Add protocol if not provided (#5866: IE7 issue with protocol-less urls)
		// We also use the url parameter if available
		s.url = ( ( url || s.url ) + "" ).replace( rhash, "" ).replace( rprotocol, ajaxLocParts[ 1 ] + "//" );

		// Extract dataTypes list
		s.dataTypes = jQuery.trim( s.dataType || "*" ).toLowerCase().split( core_rspace );

		// A cross-domain request is in order when we have a protocol:host:port mismatch
		if ( s.crossDomain == null ) {
			parts = rurl.exec( s.url.toLowerCase() );
			s.crossDomain = !!( parts &&
				( parts[ 1 ] !== ajaxLocParts[ 1 ] || parts[ 2 ] !== ajaxLocParts[ 2 ] ||
					( parts[ 3 ] || ( parts[ 1 ] === "http:" ? 80 : 443 ) ) !=
						( ajaxLocParts[ 3 ] || ( ajaxLocParts[ 1 ] === "http:" ? 80 : 443 ) ) )
			);
		}

		// Convert data if not already a string
		if ( s.data && s.processData && typeof s.data !== "string" ) {
			s.data = jQuery.param( s.data, s.traditional );
		}

		// Apply prefilters
		inspectPrefiltersOrTransports( prefilters, s, options, jqXHR );

		// If request was aborted inside a prefilter, stop there
		if ( state === 2 ) {
			return jqXHR;
		}

		// We can fire global events as of now if asked to
		fireGlobals = s.global;

		// Uppercase the type
		s.type = s.type.toUpperCase();

		// Determine if request has content
		s.hasContent = !rnoContent.test( s.type );

		// Watch for a new set of requests
		if ( fireGlobals && jQuery.active++ === 0 ) {
			jQuery.event.trigger( "ajaxStart" );
		}

		// More options handling for requests with no content
		if ( !s.hasContent ) {

			// If data is available, append data to url
			if ( s.data ) {
				s.url += ( rquery.test( s.url ) ? "&" : "?" ) + s.data;
				// #9682: remove data so that it's not used in an eventual retry
				delete s.data;
			}

			// Get ifModifiedKey before adding the anti-cache parameter
			ifModifiedKey = s.url;

			// Add anti-cache in url if needed
			if ( s.cache === false ) {

				var ts = jQuery.now(),
					// try replacing _= if it is there
					ret = s.url.replace( rts, "$1_=" + ts );

				// if nothing was replaced, add timestamp to the end
				s.url = ret + ( ( ret === s.url ) ? ( rquery.test( s.url ) ? "&" : "?" ) + "_=" + ts : "" );
			}
		}

		// Set the correct header, if data is being sent
		if ( s.data && s.hasContent && s.contentType !== false || options.contentType ) {
			jqXHR.setRequestHeader( "Content-Type", s.contentType );
		}

		// Set the If-Modified-Since and/or If-None-Match header, if in ifModified mode.
		if ( s.ifModified ) {
			ifModifiedKey = ifModifiedKey || s.url;
			if ( jQuery.lastModified[ ifModifiedKey ] ) {
				jqXHR.setRequestHeader( "If-Modified-Since", jQuery.lastModified[ ifModifiedKey ] );
			}
			if ( jQuery.etag[ ifModifiedKey ] ) {
				jqXHR.setRequestHeader( "If-None-Match", jQuery.etag[ ifModifiedKey ] );
			}
		}

		// Set the Accepts header for the server, depending on the dataType
		jqXHR.setRequestHeader(
			"Accept",
			s.dataTypes[ 0 ] && s.accepts[ s.dataTypes[0] ] ?
				s.accepts[ s.dataTypes[0] ] + ( s.dataTypes[ 0 ] !== "*" ? ", " + allTypes + "; q=0.01" : "" ) :
				s.accepts[ "*" ]
		);

		// Check for headers option
		for ( i in s.headers ) {
			jqXHR.setRequestHeader( i, s.headers[ i ] );
		}

		// Allow custom headers/mimetypes and early abort
		if ( s.beforeSend && ( s.beforeSend.call( callbackContext, jqXHR, s ) === false || state === 2 ) ) {
				// Abort if not done already and return
				return jqXHR.abort();

		}

		// aborting is no longer a cancellation
		strAbort = "abort";

		// Install callbacks on deferreds
		for ( i in { success: 1, error: 1, complete: 1 } ) {
			jqXHR[ i ]( s[ i ] );
		}

		// Get transport
		transport = inspectPrefiltersOrTransports( transports, s, options, jqXHR );

		// If no transport, we auto-abort
		if ( !transport ) {
			done( -1, "No Transport" );
		} else {
			jqXHR.readyState = 1;
			// Send global event
			if ( fireGlobals ) {
				globalEventContext.trigger( "ajaxSend", [ jqXHR, s ] );
			}
			// Timeout
			if ( s.async && s.timeout > 0 ) {
				timeoutTimer = setTimeout( function(){
					jqXHR.abort( "timeout" );
				}, s.timeout );
			}

			try {
				state = 1;
				transport.send( requestHeaders, done );
			} catch (e) {
				// Propagate exception as error if not done
				if ( state < 2 ) {
					done( -1, e );
				// Simply rethrow otherwise
				} else {
					throw e;
				}
			}
		}

		return jqXHR;
	},

	// Counter for holding the number of active queries
	active: 0,

	// Last-Modified header cache for next request
	lastModified: {},
	etag: {}

});

/* Handles responses to an ajax request:
 * - sets all responseXXX fields accordingly
 * - finds the right dataType (mediates between content-type and expected dataType)
 * - returns the corresponding response
 */
function ajaxHandleResponses( s, jqXHR, responses ) {

	var ct, type, finalDataType, firstDataType,
		contents = s.contents,
		dataTypes = s.dataTypes,
		responseFields = s.responseFields;

	// Fill responseXXX fields
	for ( type in responseFields ) {
		if ( type in responses ) {
			jqXHR[ responseFields[type] ] = responses[ type ];
		}
	}

	// Remove auto dataType and get content-type in the process
	while( dataTypes[ 0 ] === "*" ) {
		dataTypes.shift();
		if ( ct === undefined ) {
			ct = s.mimeType || jqXHR.getResponseHeader( "content-type" );
		}
	}

	// Check if we're dealing with a known content-type
	if ( ct ) {
		for ( type in contents ) {
			if ( contents[ type ] && contents[ type ].test( ct ) ) {
				dataTypes.unshift( type );
				break;
			}
		}
	}

	// Check to see if we have a response for the expected dataType
	if ( dataTypes[ 0 ] in responses ) {
		finalDataType = dataTypes[ 0 ];
	} else {
		// Try convertible dataTypes
		for ( type in responses ) {
			if ( !dataTypes[ 0 ] || s.converters[ type + " " + dataTypes[0] ] ) {
				finalDataType = type;
				break;
			}
			if ( !firstDataType ) {
				firstDataType = type;
			}
		}
		// Or just use first one
		finalDataType = finalDataType || firstDataType;
	}

	// If we found a dataType
	// We add the dataType to the list if needed
	// and return the corresponding response
	if ( finalDataType ) {
		if ( finalDataType !== dataTypes[ 0 ] ) {
			dataTypes.unshift( finalDataType );
		}
		return responses[ finalDataType ];
	}
}

// Chain conversions given the request and the original response
function ajaxConvert( s, response ) {

	var conv, conv2, current, tmp,
		// Work with a copy of dataTypes in case we need to modify it for conversion
		dataTypes = s.dataTypes.slice(),
		prev = dataTypes[ 0 ],
		converters = {},
		i = 0;

	// Apply the dataFilter if provided
	if ( s.dataFilter ) {
		response = s.dataFilter( response, s.dataType );
	}

	// Create converters map with lowercased keys
	if ( dataTypes[ 1 ] ) {
		for ( conv in s.converters ) {
			converters[ conv.toLowerCase() ] = s.converters[ conv ];
		}
	}

	// Convert to each sequential dataType, tolerating list modification
	for ( ; (current = dataTypes[++i]); ) {

		// There's only work to do if current dataType is non-auto
		if ( current !== "*" ) {

			// Convert response if prev dataType is non-auto and differs from current
			if ( prev !== "*" && prev !== current ) {

				// Seek a direct converter
				conv = converters[ prev + " " + current ] || converters[ "* " + current ];

				// If none found, seek a pair
				if ( !conv ) {
					for ( conv2 in converters ) {

						// If conv2 outputs current
						tmp = conv2.split(" ");
						if ( tmp[ 1 ] === current ) {

							// If prev can be converted to accepted input
							conv = converters[ prev + " " + tmp[ 0 ] ] ||
								converters[ "* " + tmp[ 0 ] ];
							if ( conv ) {
								// Condense equivalence converters
								if ( conv === true ) {
									conv = converters[ conv2 ];

								// Otherwise, insert the intermediate dataType
								} else if ( converters[ conv2 ] !== true ) {
									current = tmp[ 0 ];
									dataTypes.splice( i--, 0, current );
								}

								break;
							}
						}
					}
				}

				// Apply converter (if not an equivalence)
				if ( conv !== true ) {

					// Unless errors are allowed to bubble, catch and return them
					if ( conv && s["throws"] ) {
						response = conv( response );
					} else {
						try {
							response = conv( response );
						} catch ( e ) {
							return { state: "parsererror", error: conv ? e : "No conversion from " + prev + " to " + current };
						}
					}
				}
			}

			// Update prev for next iteration
			prev = current;
		}
	}

	return { state: "success", data: response };
}
var oldCallbacks = [],
	rquestion = /\?/,
	rjsonp = /(=)\?(?=&|$)|\?\?/,
	nonce = jQuery.now();

// Default jsonp settings
jQuery.ajaxSetup({
	jsonp: "callback",
	jsonpCallback: function() {
		var callback = oldCallbacks.pop() || ( jQuery.expando + "_" + ( nonce++ ) );
		this[ callback ] = true;
		return callback;
	}
});

// Detect, normalize options and install callbacks for jsonp requests
jQuery.ajaxPrefilter( "json jsonp", function( s, originalSettings, jqXHR ) {

	var callbackName, overwritten, responseContainer,
		data = s.data,
		url = s.url,
		hasCallback = s.jsonp !== false,
		replaceInUrl = hasCallback && rjsonp.test( url ),
		replaceInData = hasCallback && !replaceInUrl && typeof data === "string" &&
			!( s.contentType || "" ).indexOf("application/x-www-form-urlencoded") &&
			rjsonp.test( data );

	// Handle iff the expected data type is "jsonp" or we have a parameter to set
	if ( s.dataTypes[ 0 ] === "jsonp" || replaceInUrl || replaceInData ) {

		// Get callback name, remembering preexisting value associated with it
		callbackName = s.jsonpCallback = jQuery.isFunction( s.jsonpCallback ) ?
			s.jsonpCallback() :
			s.jsonpCallback;
		overwritten = window[ callbackName ];

		// Insert callback into url or form data
		if ( replaceInUrl ) {
			s.url = url.replace( rjsonp, "$1" + callbackName );
		} else if ( replaceInData ) {
			s.data = data.replace( rjsonp, "$1" + callbackName );
		} else if ( hasCallback ) {
			s.url += ( rquestion.test( url ) ? "&" : "?" ) + s.jsonp + "=" + callbackName;
		}

		// Use data converter to retrieve json after script execution
		s.converters["script json"] = function() {
			if ( !responseContainer ) {
				jQuery.error( callbackName + " was not called" );
			}
			return responseContainer[ 0 ];
		};

		// force json dataType
		s.dataTypes[ 0 ] = "json";

		// Install callback
		window[ callbackName ] = function() {
			responseContainer = arguments;
		};

		// Clean-up function (fires after converters)
		jqXHR.always(function() {
			// Restore preexisting value
			window[ callbackName ] = overwritten;

			// Save back as free
			if ( s[ callbackName ] ) {
				// make sure that re-using the options doesn't screw things around
				s.jsonpCallback = originalSettings.jsonpCallback;

				// save the callback name for future use
				oldCallbacks.push( callbackName );
			}

			// Call if it was a function and we have a response
			if ( responseContainer && jQuery.isFunction( overwritten ) ) {
				overwritten( responseContainer[ 0 ] );
			}

			responseContainer = overwritten = undefined;
		});

		// Delegate to script
		return "script";
	}
});
// Install script dataType
jQuery.ajaxSetup({
	accepts: {
		script: "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript"
	},
	contents: {
		script: /javascript|ecmascript/
	},
	converters: {
		"text script": function( text ) {
			jQuery.globalEval( text );
			return text;
		}
	}
});

// Handle cache's special case and global
jQuery.ajaxPrefilter( "script", function( s ) {
	if ( s.cache === undefined ) {
		s.cache = false;
	}
	if ( s.crossDomain ) {
		s.type = "GET";
		s.global = false;
	}
});

// Bind script tag hack transport
jQuery.ajaxTransport( "script", function(s) {

	// This transport only deals with cross domain requests
	if ( s.crossDomain ) {

		var script,
			head = document.head || document.getElementsByTagName( "head" )[0] || document.documentElement;

		return {

			send: function( _, callback ) {

				script = document.createElement( "script" );

				script.async = "async";

				if ( s.scriptCharset ) {
					script.charset = s.scriptCharset;
				}

				script.src = s.url;

				// Attach handlers for all browsers
				script.onload = script.onreadystatechange = function( _, isAbort ) {

					if ( isAbort || !script.readyState || /loaded|complete/.test( script.readyState ) ) {

						// Handle memory leak in IE
						script.onload = script.onreadystatechange = null;

						// Remove the script
						if ( head && script.parentNode ) {
							head.removeChild( script );
						}

						// Dereference the script
						script = undefined;

						// Callback if not abort
						if ( !isAbort ) {
							callback( 200, "success" );
						}
					}
				};
				// Use insertBefore instead of appendChild  to circumvent an IE6 bug.
				// This arises when a base node is used (#2709 and #4378).
				head.insertBefore( script, head.firstChild );
			},

			abort: function() {
				if ( script ) {
					script.onload( 0, 1 );
				}
			}
		};
	}
});
var xhrCallbacks,
	// #5280: Internet Explorer will keep connections alive if we don't abort on unload
	xhrOnUnloadAbort = window.ActiveXObject ? function() {
		// Abort all pending requests
		for ( var key in xhrCallbacks ) {
			xhrCallbacks[ key ]( 0, 1 );
		}
	} : false,
	xhrId = 0;

// Functions to create xhrs
function createStandardXHR() {
	try {
		return new window.XMLHttpRequest();
	} catch( e ) {}
}

function createActiveXHR() {
	try {
		return new window.ActiveXObject( "Microsoft.XMLHTTP" );
	} catch( e ) {}
}

// Create the request object
// (This is still attached to ajaxSettings for backward compatibility)
jQuery.ajaxSettings.xhr = window.ActiveXObject ?
	/* Microsoft failed to properly
	 * implement the XMLHttpRequest in IE7 (can't request local files),
	 * so we use the ActiveXObject when it is available
	 * Additionally XMLHttpRequest can be disabled in IE7/IE8 so
	 * we need a fallback.
	 */
	function() {
		return !this.isLocal && createStandardXHR() || createActiveXHR();
	} :
	// For all other browsers, use the standard XMLHttpRequest object
	createStandardXHR;

// Determine support properties
(function( xhr ) {
	jQuery.extend( jQuery.support, {
		ajax: !!xhr,
		cors: !!xhr && ( "withCredentials" in xhr )
	});
})( jQuery.ajaxSettings.xhr() );

// Create transport if the browser can provide an xhr
if ( jQuery.support.ajax ) {

	jQuery.ajaxTransport(function( s ) {
		// Cross domain only allowed if supported through XMLHttpRequest
		if ( !s.crossDomain || jQuery.support.cors ) {

			var callback;

			return {
				send: function( headers, complete ) {

					// Get a new xhr
					var handle, i,
						xhr = s.xhr();

					// Open the socket
					// Passing null username, generates a login popup on Opera (#2865)
					if ( s.username ) {
						xhr.open( s.type, s.url, s.async, s.username, s.password );
					} else {
						xhr.open( s.type, s.url, s.async );
					}

					// Apply custom fields if provided
					if ( s.xhrFields ) {
						for ( i in s.xhrFields ) {
							xhr[ i ] = s.xhrFields[ i ];
						}
					}

					// Override mime type if needed
					if ( s.mimeType && xhr.overrideMimeType ) {
						xhr.overrideMimeType( s.mimeType );
					}

					// X-Requested-With header
					// For cross-domain requests, seeing as conditions for a preflight are
					// akin to a jigsaw puzzle, we simply never set it to be sure.
					// (it can always be set on a per-request basis or even using ajaxSetup)
					// For same-domain requests, won't change header if already provided.
					if ( !s.crossDomain && !headers["X-Requested-With"] ) {
						headers[ "X-Requested-With" ] = "XMLHttpRequest";
					}

					// Need an extra try/catch for cross domain requests in Firefox 3
					try {
						for ( i in headers ) {
							xhr.setRequestHeader( i, headers[ i ] );
						}
					} catch( _ ) {}

					// Do send the request
					// This may raise an exception which is actually
					// handled in jQuery.ajax (so no try/catch here)
					xhr.send( ( s.hasContent && s.data ) || null );

					// Listener
					callback = function( _, isAbort ) {

						var status,
							statusText,
							responseHeaders,
							responses,
							xml;

						// Firefox throws exceptions when accessing properties
						// of an xhr when a network error occurred
						// http://helpful.knobs-dials.com/index.php/Component_returned_failure_code:_0x80040111_(NS_ERROR_NOT_AVAILABLE)
						try {

							// Was never called and is aborted or complete
							if ( callback && ( isAbort || xhr.readyState === 4 ) ) {

								// Only called once
								callback = undefined;

								// Do not keep as active anymore
								if ( handle ) {
									xhr.onreadystatechange = jQuery.noop;
									if ( xhrOnUnloadAbort ) {
										delete xhrCallbacks[ handle ];
									}
								}

								// If it's an abort
								if ( isAbort ) {
									// Abort it manually if needed
									if ( xhr.readyState !== 4 ) {
										xhr.abort();
									}
								} else {
									status = xhr.status;
									responseHeaders = xhr.getAllResponseHeaders();
									responses = {};
									xml = xhr.responseXML;

									// Construct response list
									if ( xml && xml.documentElement /* #4958 */ ) {
										responses.xml = xml;
									}

									// When requesting binary data, IE6-9 will throw an exception
									// on any attempt to access responseText (#11426)
									try {
										responses.text = xhr.responseText;
									} catch( e ) {
									}

									// Firefox throws an exception when accessing
									// statusText for faulty cross-domain requests
									try {
										statusText = xhr.statusText;
									} catch( e ) {
										// We normalize with Webkit giving an empty statusText
										statusText = "";
									}

									// Filter status for non standard behaviors

									// If the request is local and we have data: assume a success
									// (success with no data won't get notified, that's the best we
									// can do given current implementations)
									if ( !status && s.isLocal && !s.crossDomain ) {
										status = responses.text ? 200 : 404;
									// IE - #1450: sometimes returns 1223 when it should be 204
									} else if ( status === 1223 ) {
										status = 204;
									}
								}
							}
						} catch( firefoxAccessException ) {
							if ( !isAbort ) {
								complete( -1, firefoxAccessException );
							}
						}

						// Call complete if needed
						if ( responses ) {
							complete( status, statusText, responses, responseHeaders );
						}
					};

					if ( !s.async ) {
						// if we're in sync mode we fire the callback
						callback();
					} else if ( xhr.readyState === 4 ) {
						// (IE6 & IE7) if it's in cache and has been
						// retrieved directly we need to fire the callback
						setTimeout( callback, 0 );
					} else {
						handle = ++xhrId;
						if ( xhrOnUnloadAbort ) {
							// Create the active xhrs callbacks list if needed
							// and attach the unload handler
							if ( !xhrCallbacks ) {
								xhrCallbacks = {};
								jQuery( window ).unload( xhrOnUnloadAbort );
							}
							// Add to list of active xhrs callbacks
							xhrCallbacks[ handle ] = callback;
						}
						xhr.onreadystatechange = callback;
					}
				},

				abort: function() {
					if ( callback ) {
						callback(0,1);
					}
				}
			};
		}
	});
}
var fxNow, timerId,
	rfxtypes = /^(?:toggle|show|hide)$/,
	rfxnum = new RegExp( "^(?:([-+])=|)(" + core_pnum + ")([a-z%]*)$", "i" ),
	rrun = /queueHooks$/,
	animationPrefilters = [ defaultPrefilter ],
	tweeners = {
		"*": [function( prop, value ) {
			var end, unit,
				tween = this.createTween( prop, value ),
				parts = rfxnum.exec( value ),
				target = tween.cur(),
				start = +target || 0,
				scale = 1,
				maxIterations = 20;

			if ( parts ) {
				end = +parts[2];
				unit = parts[3] || ( jQuery.cssNumber[ prop ] ? "" : "px" );

				// We need to compute starting value
				if ( unit !== "px" && start ) {
					// Iteratively approximate from a nonzero starting point
					// Prefer the current property, because this process will be trivial if it uses the same units
					// Fallback to end or a simple constant
					start = jQuery.css( tween.elem, prop, true ) || end || 1;

					do {
						// If previous iteration zeroed out, double until we get *something*
						// Use a string for doubling factor so we don't accidentally see scale as unchanged below
						scale = scale || ".5";

						// Adjust and apply
						start = start / scale;
						jQuery.style( tween.elem, prop, start + unit );

					// Update scale, tolerating zero or NaN from tween.cur()
					// And breaking the loop if scale is unchanged or perfect, or if we've just had enough
					} while ( scale !== (scale = tween.cur() / target) && scale !== 1 && --maxIterations );
				}

				tween.unit = unit;
				tween.start = start;
				// If a +=/-= token was provided, we're doing a relative animation
				tween.end = parts[1] ? start + ( parts[1] + 1 ) * end : end;
			}
			return tween;
		}]
	};

// Animations created synchronously will run synchronously
function createFxNow() {
	setTimeout(function() {
		fxNow = undefined;
	}, 0 );
	return ( fxNow = jQuery.now() );
}

function createTweens( animation, props ) {
	jQuery.each( props, function( prop, value ) {
		var collection = ( tweeners[ prop ] || [] ).concat( tweeners[ "*" ] ),
			index = 0,
			length = collection.length;
		for ( ; index < length; index++ ) {
			if ( collection[ index ].call( animation, prop, value ) ) {

				// we're done with this property
				return;
			}
		}
	});
}

function Animation( elem, properties, options ) {
	var result,
		index = 0,
		tweenerIndex = 0,
		length = animationPrefilters.length,
		deferred = jQuery.Deferred().always( function() {
			// don't match elem in the :animated selector
			delete tick.elem;
		}),
		tick = function() {
			var currentTime = fxNow || createFxNow(),
				remaining = Math.max( 0, animation.startTime + animation.duration - currentTime ),
				// archaic crash bug won't allow us to use 1 - ( 0.5 || 0 ) (#12497)
				temp = remaining / animation.duration || 0,
				percent = 1 - temp,
				index = 0,
				length = animation.tweens.length;

			for ( ; index < length ; index++ ) {
				animation.tweens[ index ].run( percent );
			}

			deferred.notifyWith( elem, [ animation, percent, remaining ]);

			if ( percent < 1 && length ) {
				return remaining;
			} else {
				deferred.resolveWith( elem, [ animation ] );
				return false;
			}
		},
		animation = deferred.promise({
			elem: elem,
			props: jQuery.extend( {}, properties ),
			opts: jQuery.extend( true, { specialEasing: {} }, options ),
			originalProperties: properties,
			originalOptions: options,
			startTime: fxNow || createFxNow(),
			duration: options.duration,
			tweens: [],
			createTween: function( prop, end, easing ) {
				var tween = jQuery.Tween( elem, animation.opts, prop, end,
						animation.opts.specialEasing[ prop ] || animation.opts.easing );
				animation.tweens.push( tween );
				return tween;
			},
			stop: function( gotoEnd ) {
				var index = 0,
					// if we are going to the end, we want to run all the tweens
					// otherwise we skip this part
					length = gotoEnd ? animation.tweens.length : 0;

				for ( ; index < length ; index++ ) {
					animation.tweens[ index ].run( 1 );
				}

				// resolve when we played the last frame
				// otherwise, reject
				if ( gotoEnd ) {
					deferred.resolveWith( elem, [ animation, gotoEnd ] );
				} else {
					deferred.rejectWith( elem, [ animation, gotoEnd ] );
				}
				return this;
			}
		}),
		props = animation.props;

	propFilter( props, animation.opts.specialEasing );

	for ( ; index < length ; index++ ) {
		result = animationPrefilters[ index ].call( animation, elem, props, animation.opts );
		if ( result ) {
			return result;
		}
	}

	createTweens( animation, props );

	if ( jQuery.isFunction( animation.opts.start ) ) {
		animation.opts.start.call( elem, animation );
	}

	jQuery.fx.timer(
		jQuery.extend( tick, {
			anim: animation,
			queue: animation.opts.queue,
			elem: elem
		})
	);

	// attach callbacks from options
	return animation.progress( animation.opts.progress )
		.done( animation.opts.done, animation.opts.complete )
		.fail( animation.opts.fail )
		.always( animation.opts.always );
}

function propFilter( props, specialEasing ) {
	var index, name, easing, value, hooks;

	// camelCase, specialEasing and expand cssHook pass
	for ( index in props ) {
		name = jQuery.camelCase( index );
		easing = specialEasing[ name ];
		value = props[ index ];
		if ( jQuery.isArray( value ) ) {
			easing = value[ 1 ];
			value = props[ index ] = value[ 0 ];
		}

		if ( index !== name ) {
			props[ name ] = value;
			delete props[ index ];
		}

		hooks = jQuery.cssHooks[ name ];
		if ( hooks && "expand" in hooks ) {
			value = hooks.expand( value );
			delete props[ name ];

			// not quite $.extend, this wont overwrite keys already present.
			// also - reusing 'index' from above because we have the correct "name"
			for ( index in value ) {
				if ( !( index in props ) ) {
					props[ index ] = value[ index ];
					specialEasing[ index ] = easing;
				}
			}
		} else {
			specialEasing[ name ] = easing;
		}
	}
}

jQuery.Animation = jQuery.extend( Animation, {

	tweener: function( props, callback ) {
		if ( jQuery.isFunction( props ) ) {
			callback = props;
			props = [ "*" ];
		} else {
			props = props.split(" ");
		}

		var prop,
			index = 0,
			length = props.length;

		for ( ; index < length ; index++ ) {
			prop = props[ index ];
			tweeners[ prop ] = tweeners[ prop ] || [];
			tweeners[ prop ].unshift( callback );
		}
	},

	prefilter: function( callback, prepend ) {
		if ( prepend ) {
			animationPrefilters.unshift( callback );
		} else {
			animationPrefilters.push( callback );
		}
	}
});

function defaultPrefilter( elem, props, opts ) {
	var index, prop, value, length, dataShow, toggle, tween, hooks, oldfire,
		anim = this,
		style = elem.style,
		orig = {},
		handled = [],
		hidden = elem.nodeType && isHidden( elem );

	// handle queue: false promises
	if ( !opts.queue ) {
		hooks = jQuery._queueHooks( elem, "fx" );
		if ( hooks.unqueued == null ) {
			hooks.unqueued = 0;
			oldfire = hooks.empty.fire;
			hooks.empty.fire = function() {
				if ( !hooks.unqueued ) {
					oldfire();
				}
			};
		}
		hooks.unqueued++;

		anim.always(function() {
			// doing this makes sure that the complete handler will be called
			// before this completes
			anim.always(function() {
				hooks.unqueued--;
				if ( !jQuery.queue( elem, "fx" ).length ) {
					hooks.empty.fire();
				}
			});
		});
	}

	// height/width overflow pass
	if ( elem.nodeType === 1 && ( "height" in props || "width" in props ) ) {
		// Make sure that nothing sneaks out
		// Record all 3 overflow attributes because IE does not
		// change the overflow attribute when overflowX and
		// overflowY are set to the same value
		opts.overflow = [ style.overflow, style.overflowX, style.overflowY ];

		// Set display property to inline-block for height/width
		// animations on inline elements that are having width/height animated
		if ( jQuery.css( elem, "display" ) === "inline" &&
				jQuery.css( elem, "float" ) === "none" ) {

			// inline-level elements accept inline-block;
			// block-level elements need to be inline with layout
			if ( !jQuery.support.inlineBlockNeedsLayout || css_defaultDisplay( elem.nodeName ) === "inline" ) {
				style.display = "inline-block";

			} else {
				style.zoom = 1;
			}
		}
	}

	if ( opts.overflow ) {
		style.overflow = "hidden";
		if ( !jQuery.support.shrinkWrapBlocks ) {
			anim.done(function() {
				style.overflow = opts.overflow[ 0 ];
				style.overflowX = opts.overflow[ 1 ];
				style.overflowY = opts.overflow[ 2 ];
			});
		}
	}


	// show/hide pass
	for ( index in props ) {
		value = props[ index ];
		if ( rfxtypes.exec( value ) ) {
			delete props[ index ];
			toggle = toggle || value === "toggle";
			if ( value === ( hidden ? "hide" : "show" ) ) {
				continue;
			}
			handled.push( index );
		}
	}

	length = handled.length;
	if ( length ) {
		dataShow = jQuery._data( elem, "fxshow" ) || jQuery._data( elem, "fxshow", {} );
		if ( "hidden" in dataShow ) {
			hidden = dataShow.hidden;
		}

		// store state if its toggle - enables .stop().toggle() to "reverse"
		if ( toggle ) {
			dataShow.hidden = !hidden;
		}
		if ( hidden ) {
			jQuery( elem ).show();
		} else {
			anim.done(function() {
				jQuery( elem ).hide();
			});
		}
		anim.done(function() {
			var prop;
			jQuery.removeData( elem, "fxshow", true );
			for ( prop in orig ) {
				jQuery.style( elem, prop, orig[ prop ] );
			}
		});
		for ( index = 0 ; index < length ; index++ ) {
			prop = handled[ index ];
			tween = anim.createTween( prop, hidden ? dataShow[ prop ] : 0 );
			orig[ prop ] = dataShow[ prop ] || jQuery.style( elem, prop );

			if ( !( prop in dataShow ) ) {
				dataShow[ prop ] = tween.start;
				if ( hidden ) {
					tween.end = tween.start;
					tween.start = prop === "width" || prop === "height" ? 1 : 0;
				}
			}
		}
	}
}

function Tween( elem, options, prop, end, easing ) {
	return new Tween.prototype.init( elem, options, prop, end, easing );
}
jQuery.Tween = Tween;

Tween.prototype = {
	constructor: Tween,
	init: function( elem, options, prop, end, easing, unit ) {
		this.elem = elem;
		this.prop = prop;
		this.easing = easing || "swing";
		this.options = options;
		this.start = this.now = this.cur();
		this.end = end;
		this.unit = unit || ( jQuery.cssNumber[ prop ] ? "" : "px" );
	},
	cur: function() {
		var hooks = Tween.propHooks[ this.prop ];

		return hooks && hooks.get ?
			hooks.get( this ) :
			Tween.propHooks._default.get( this );
	},
	run: function( percent ) {
		var eased,
			hooks = Tween.propHooks[ this.prop ];

		if ( this.options.duration ) {
			this.pos = eased = jQuery.easing[ this.easing ](
				percent, this.options.duration * percent, 0, 1, this.options.duration
			);
		} else {
			this.pos = eased = percent;
		}
		this.now = ( this.end - this.start ) * eased + this.start;

		if ( this.options.step ) {
			this.options.step.call( this.elem, this.now, this );
		}

		if ( hooks && hooks.set ) {
			hooks.set( this );
		} else {
			Tween.propHooks._default.set( this );
		}
		return this;
	}
};

Tween.prototype.init.prototype = Tween.prototype;

Tween.propHooks = {
	_default: {
		get: function( tween ) {
			var result;

			if ( tween.elem[ tween.prop ] != null &&
				(!tween.elem.style || tween.elem.style[ tween.prop ] == null) ) {
				return tween.elem[ tween.prop ];
			}

			// passing any value as a 4th parameter to .css will automatically
			// attempt a parseFloat and fallback to a string if the parse fails
			// so, simple values such as "10px" are parsed to Float.
			// complex values such as "rotate(1rad)" are returned as is.
			result = jQuery.css( tween.elem, tween.prop, false, "" );
			// Empty strings, null, undefined and "auto" are converted to 0.
			return !result || result === "auto" ? 0 : result;
		},
		set: function( tween ) {
			// use step hook for back compat - use cssHook if its there - use .style if its
			// available and use plain properties where available
			if ( jQuery.fx.step[ tween.prop ] ) {
				jQuery.fx.step[ tween.prop ]( tween );
			} else if ( tween.elem.style && ( tween.elem.style[ jQuery.cssProps[ tween.prop ] ] != null || jQuery.cssHooks[ tween.prop ] ) ) {
				jQuery.style( tween.elem, tween.prop, tween.now + tween.unit );
			} else {
				tween.elem[ tween.prop ] = tween.now;
			}
		}
	}
};

// Remove in 2.0 - this supports IE8's panic based approach
// to setting things on disconnected nodes

Tween.propHooks.scrollTop = Tween.propHooks.scrollLeft = {
	set: function( tween ) {
		if ( tween.elem.nodeType && tween.elem.parentNode ) {
			tween.elem[ tween.prop ] = tween.now;
		}
	}
};

jQuery.each([ "toggle", "show", "hide" ], function( i, name ) {
	var cssFn = jQuery.fn[ name ];
	jQuery.fn[ name ] = function( speed, easing, callback ) {
		return speed == null || typeof speed === "boolean" ||
			// special check for .toggle( handler, handler, ... )
			( !i && jQuery.isFunction( speed ) && jQuery.isFunction( easing ) ) ?
			cssFn.apply( this, arguments ) :
			this.animate( genFx( name, true ), speed, easing, callback );
	};
});

jQuery.fn.extend({
	fadeTo: function( speed, to, easing, callback ) {

		// show any hidden elements after setting opacity to 0
		return this.filter( isHidden ).css( "opacity", 0 ).show()

			// animate to the value specified
			.end().animate({ opacity: to }, speed, easing, callback );
	},
	animate: function( prop, speed, easing, callback ) {
		var empty = jQuery.isEmptyObject( prop ),
			optall = jQuery.speed( speed, easing, callback ),
			doAnimation = function() {
				// Operate on a copy of prop so per-property easing won't be lost
				var anim = Animation( this, jQuery.extend( {}, prop ), optall );

				// Empty animations resolve immediately
				if ( empty ) {
					anim.stop( true );
				}
			};

		return empty || optall.queue === false ?
			this.each( doAnimation ) :
			this.queue( optall.queue, doAnimation );
	},
	stop: function( type, clearQueue, gotoEnd ) {
		var stopQueue = function( hooks ) {
			var stop = hooks.stop;
			delete hooks.stop;
			stop( gotoEnd );
		};

		if ( typeof type !== "string" ) {
			gotoEnd = clearQueue;
			clearQueue = type;
			type = undefined;
		}
		if ( clearQueue && type !== false ) {
			this.queue( type || "fx", [] );
		}

		return this.each(function() {
			var dequeue = true,
				index = type != null && type + "queueHooks",
				timers = jQuery.timers,
				data = jQuery._data( this );

			if ( index ) {
				if ( data[ index ] && data[ index ].stop ) {
					stopQueue( data[ index ] );
				}
			} else {
				for ( index in data ) {
					if ( data[ index ] && data[ index ].stop && rrun.test( index ) ) {
						stopQueue( data[ index ] );
					}
				}
			}

			for ( index = timers.length; index--; ) {
				if ( timers[ index ].elem === this && (type == null || timers[ index ].queue === type) ) {
					timers[ index ].anim.stop( gotoEnd );
					dequeue = false;
					timers.splice( index, 1 );
				}
			}

			// start the next in the queue if the last step wasn't forced
			// timers currently will call their complete callbacks, which will dequeue
			// but only if they were gotoEnd
			if ( dequeue || !gotoEnd ) {
				jQuery.dequeue( this, type );
			}
		});
	}
});

// Generate parameters to create a standard animation
function genFx( type, includeWidth ) {
	var which,
		attrs = { height: type },
		i = 0;

	// if we include width, step value is 1 to do all cssExpand values,
	// if we don't include width, step value is 2 to skip over Left and Right
	includeWidth = includeWidth? 1 : 0;
	for( ; i < 4 ; i += 2 - includeWidth ) {
		which = cssExpand[ i ];
		attrs[ "margin" + which ] = attrs[ "padding" + which ] = type;
	}

	if ( includeWidth ) {
		attrs.opacity = attrs.width = type;
	}

	return attrs;
}

// Generate shortcuts for custom animations
jQuery.each({
	slideDown: genFx("show"),
	slideUp: genFx("hide"),
	slideToggle: genFx("toggle"),
	fadeIn: { opacity: "show" },
	fadeOut: { opacity: "hide" },
	fadeToggle: { opacity: "toggle" }
}, function( name, props ) {
	jQuery.fn[ name ] = function( speed, easing, callback ) {
		return this.animate( props, speed, easing, callback );
	};
});

jQuery.speed = function( speed, easing, fn ) {
	var opt = speed && typeof speed === "object" ? jQuery.extend( {}, speed ) : {
		complete: fn || !fn && easing ||
			jQuery.isFunction( speed ) && speed,
		duration: speed,
		easing: fn && easing || easing && !jQuery.isFunction( easing ) && easing
	};

	opt.duration = jQuery.fx.off ? 0 : typeof opt.duration === "number" ? opt.duration :
		opt.duration in jQuery.fx.speeds ? jQuery.fx.speeds[ opt.duration ] : jQuery.fx.speeds._default;

	// normalize opt.queue - true/undefined/null -> "fx"
	if ( opt.queue == null || opt.queue === true ) {
		opt.queue = "fx";
	}

	// Queueing
	opt.old = opt.complete;

	opt.complete = function() {
		if ( jQuery.isFunction( opt.old ) ) {
			opt.old.call( this );
		}

		if ( opt.queue ) {
			jQuery.dequeue( this, opt.queue );
		}
	};

	return opt;
};

jQuery.easing = {
	linear: function( p ) {
		return p;
	},
	swing: function( p ) {
		return 0.5 - Math.cos( p*Math.PI ) / 2;
	}
};

jQuery.timers = [];
jQuery.fx = Tween.prototype.init;
jQuery.fx.tick = function() {
	var timer,
		timers = jQuery.timers,
		i = 0;

	fxNow = jQuery.now();

	for ( ; i < timers.length; i++ ) {
		timer = timers[ i ];
		// Checks the timer has not already been removed
		if ( !timer() && timers[ i ] === timer ) {
			timers.splice( i--, 1 );
		}
	}

	if ( !timers.length ) {
		jQuery.fx.stop();
	}
	fxNow = undefined;
};

jQuery.fx.timer = function( timer ) {
	if ( timer() && jQuery.timers.push( timer ) && !timerId ) {
		timerId = setInterval( jQuery.fx.tick, jQuery.fx.interval );
	}
};

jQuery.fx.interval = 13;

jQuery.fx.stop = function() {
	clearInterval( timerId );
	timerId = null;
};

jQuery.fx.speeds = {
	slow: 600,
	fast: 200,
	// Default speed
	_default: 400
};

// Back Compat <1.8 extension point
jQuery.fx.step = {};

if ( jQuery.expr && jQuery.expr.filters ) {
	jQuery.expr.filters.animated = function( elem ) {
		return jQuery.grep(jQuery.timers, function( fn ) {
			return elem === fn.elem;
		}).length;
	};
}
var rroot = /^(?:body|html)$/i;

jQuery.fn.offset = function( options ) {
	if ( arguments.length ) {
		return options === undefined ?
			this :
			this.each(function( i ) {
				jQuery.offset.setOffset( this, options, i );
			});
	}

	var docElem, body, win, clientTop, clientLeft, scrollTop, scrollLeft,
		box = { top: 0, left: 0 },
		elem = this[ 0 ],
		doc = elem && elem.ownerDocument;

	if ( !doc ) {
		return;
	}

	if ( (body = doc.body) === elem ) {
		return jQuery.offset.bodyOffset( elem );
	}

	docElem = doc.documentElement;

	// Make sure it's not a disconnected DOM node
	if ( !jQuery.contains( docElem, elem ) ) {
		return box;
	}

	// If we don't have gBCR, just use 0,0 rather than error
	// BlackBerry 5, iOS 3 (original iPhone)
	if ( typeof elem.getBoundingClientRect !== "undefined" ) {
		box = elem.getBoundingClientRect();
	}
	win = getWindow( doc );
	clientTop  = docElem.clientTop  || body.clientTop  || 0;
	clientLeft = docElem.clientLeft || body.clientLeft || 0;
	scrollTop  = win.pageYOffset || docElem.scrollTop;
	scrollLeft = win.pageXOffset || docElem.scrollLeft;
	return {
		top: box.top  + scrollTop  - clientTop,
		left: box.left + scrollLeft - clientLeft
	};
};

jQuery.offset = {

	bodyOffset: function( body ) {
		var top = body.offsetTop,
			left = body.offsetLeft;

		if ( jQuery.support.doesNotIncludeMarginInBodyOffset ) {
			top  += parseFloat( jQuery.css(body, "marginTop") ) || 0;
			left += parseFloat( jQuery.css(body, "marginLeft") ) || 0;
		}

		return { top: top, left: left };
	},

	setOffset: function( elem, options, i ) {
		var position = jQuery.css( elem, "position" );

		// set position first, in-case top/left are set even on static elem
		if ( position === "static" ) {
			elem.style.position = "relative";
		}

		var curElem = jQuery( elem ),
			curOffset = curElem.offset(),
			curCSSTop = jQuery.css( elem, "top" ),
			curCSSLeft = jQuery.css( elem, "left" ),
			calculatePosition = ( position === "absolute" || position === "fixed" ) && jQuery.inArray("auto", [curCSSTop, curCSSLeft]) > -1,
			props = {}, curPosition = {}, curTop, curLeft;

		// need to be able to calculate position if either top or left is auto and position is either absolute or fixed
		if ( calculatePosition ) {
			curPosition = curElem.position();
			curTop = curPosition.top;
			curLeft = curPosition.left;
		} else {
			curTop = parseFloat( curCSSTop ) || 0;
			curLeft = parseFloat( curCSSLeft ) || 0;
		}

		if ( jQuery.isFunction( options ) ) {
			options = options.call( elem, i, curOffset );
		}

		if ( options.top != null ) {
			props.top = ( options.top - curOffset.top ) + curTop;
		}
		if ( options.left != null ) {
			props.left = ( options.left - curOffset.left ) + curLeft;
		}

		if ( "using" in options ) {
			options.using.call( elem, props );
		} else {
			curElem.css( props );
		}
	}
};


jQuery.fn.extend({

	position: function() {
		if ( !this[0] ) {
			return;
		}

		var elem = this[0],

		// Get *real* offsetParent
		offsetParent = this.offsetParent(),

		// Get correct offsets
		offset       = this.offset(),
		parentOffset = rroot.test(offsetParent[0].nodeName) ? { top: 0, left: 0 } : offsetParent.offset();

		// Subtract element margins
		// note: when an element has margin: auto the offsetLeft and marginLeft
		// are the same in Safari causing offset.left to incorrectly be 0
		offset.top  -= parseFloat( jQuery.css(elem, "marginTop") ) || 0;
		offset.left -= parseFloat( jQuery.css(elem, "marginLeft") ) || 0;

		// Add offsetParent borders
		parentOffset.top  += parseFloat( jQuery.css(offsetParent[0], "borderTopWidth") ) || 0;
		parentOffset.left += parseFloat( jQuery.css(offsetParent[0], "borderLeftWidth") ) || 0;

		// Subtract the two offsets
		return {
			top:  offset.top  - parentOffset.top,
			left: offset.left - parentOffset.left
		};
	},

	offsetParent: function() {
		return this.map(function() {
			var offsetParent = this.offsetParent || document.body;
			while ( offsetParent && (!rroot.test(offsetParent.nodeName) && jQuery.css(offsetParent, "position") === "static") ) {
				offsetParent = offsetParent.offsetParent;
			}
			return offsetParent || document.body;
		});
	}
});


// Create scrollLeft and scrollTop methods
jQuery.each( {scrollLeft: "pageXOffset", scrollTop: "pageYOffset"}, function( method, prop ) {
	var top = /Y/.test( prop );

	jQuery.fn[ method ] = function( val ) {
		return jQuery.access( this, function( elem, method, val ) {
			var win = getWindow( elem );

			if ( val === undefined ) {
				return win ? (prop in win) ? win[ prop ] :
					win.document.documentElement[ method ] :
					elem[ method ];
			}

			if ( win ) {
				win.scrollTo(
					!top ? val : jQuery( win ).scrollLeft(),
					 top ? val : jQuery( win ).scrollTop()
				);

			} else {
				elem[ method ] = val;
			}
		}, method, val, arguments.length, null );
	};
});

function getWindow( elem ) {
	return jQuery.isWindow( elem ) ?
		elem :
		elem.nodeType === 9 ?
			elem.defaultView || elem.parentWindow :
			false;
}
// Create innerHeight, innerWidth, height, width, outerHeight and outerWidth methods
jQuery.each( { Height: "height", Width: "width" }, function( name, type ) {
	jQuery.each( { padding: "inner" + name, content: type, "": "outer" + name }, function( defaultExtra, funcName ) {
		// margin is only for outerHeight, outerWidth
		jQuery.fn[ funcName ] = function( margin, value ) {
			var chainable = arguments.length && ( defaultExtra || typeof margin !== "boolean" ),
				extra = defaultExtra || ( margin === true || value === true ? "margin" : "border" );

			return jQuery.access( this, function( elem, type, value ) {
				var doc;

				if ( jQuery.isWindow( elem ) ) {
					// As of 5/8/2012 this will yield incorrect results for Mobile Safari, but there
					// isn't a whole lot we can do. See pull request at this URL for discussion:
					// https://github.com/jquery/jquery/pull/764
					return elem.document.documentElement[ "client" + name ];
				}

				// Get document width or height
				if ( elem.nodeType === 9 ) {
					doc = elem.documentElement;

					// Either scroll[Width/Height] or offset[Width/Height] or client[Width/Height], whichever is greatest
					// unfortunately, this causes bug #3838 in IE6/8 only, but there is currently no good, small way to fix it.
					return Math.max(
						elem.body[ "scroll" + name ], doc[ "scroll" + name ],
						elem.body[ "offset" + name ], doc[ "offset" + name ],
						doc[ "client" + name ]
					);
				}

				return value === undefined ?
					// Get width or height on the element, requesting but not forcing parseFloat
					jQuery.css( elem, type, value, extra ) :

					// Set width or height on the element
					jQuery.style( elem, type, value, extra );
			}, type, chainable ? margin : undefined, chainable, null );
		};
	});
});
// Expose jQuery to the global object
window.jQuery = window.$ = jQuery;

// Expose jQuery as an AMD module, but only for AMD loaders that
// understand the issues with loading multiple versions of jQuery
// in a page that all might call define(). The loader will indicate
// they have special allowances for multiple jQuery versions by
// specifying define.amd.jQuery = true. Register as a named module,
// since jQuery can be concatenated with other files that may use define,
// but not use a proper concatenation script that understands anonymous
// AMD modules. A named AMD is safest and most robust way to register.
// Lowercase jquery is used because AMD module names are derived from
// file names, and jQuery is normally delivered in a lowercase file name.
// Do this after creating the global so that if an AMD module wants to call
// noConflict to hide this version of jQuery, it will work.
if ( typeof define === "function" && define.amd && define.amd.jQuery ) {
	define( "jquery", [], function () { return jQuery; } );
}

})( window );
/* ========================================================================
 * Bootstrap: affix.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#affix
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // AFFIX CLASS DEFINITION
  // ======================

  var Affix = function (element, options) {
    this.options = $.extend({}, Affix.DEFAULTS, options)

    var target = this.options.target === Affix.DEFAULTS.target ? $(this.options.target) : $(document).find(this.options.target)

    this.$target = target
      .on('scroll.bs.affix.data-api', $.proxy(this.checkPosition, this))
      .on('click.bs.affix.data-api',  $.proxy(this.checkPositionWithEventLoop, this))

    this.$element     = $(element)
    this.affixed      = null
    this.unpin        = null
    this.pinnedOffset = null

    this.checkPosition()
  }

  Affix.VERSION  = '3.4.1'

  Affix.RESET    = 'affix affix-top affix-bottom'

  Affix.DEFAULTS = {
    offset: 0,
    target: window
  }

  Affix.prototype.getState = function (scrollHeight, height, offsetTop, offsetBottom) {
    var scrollTop    = this.$target.scrollTop()
    var position     = this.$element.offset()
    var targetHeight = this.$target.height()

    if (offsetTop != null && this.affixed == 'top') return scrollTop < offsetTop ? 'top' : false

    if (this.affixed == 'bottom') {
      if (offsetTop != null) return (scrollTop + this.unpin <= position.top) ? false : 'bottom'
      return (scrollTop + targetHeight <= scrollHeight - offsetBottom) ? false : 'bottom'
    }

    var initializing   = this.affixed == null
    var colliderTop    = initializing ? scrollTop : position.top
    var colliderHeight = initializing ? targetHeight : height

    if (offsetTop != null && scrollTop <= offsetTop) return 'top'
    if (offsetBottom != null && (colliderTop + colliderHeight >= scrollHeight - offsetBottom)) return 'bottom'

    return false
  }

  Affix.prototype.getPinnedOffset = function () {
    if (this.pinnedOffset) return this.pinnedOffset
    this.$element.removeClass(Affix.RESET).addClass('affix')
    var scrollTop = this.$target.scrollTop()
    var position  = this.$element.offset()
    return (this.pinnedOffset = position.top - scrollTop)
  }

  Affix.prototype.checkPositionWithEventLoop = function () {
    setTimeout($.proxy(this.checkPosition, this), 1)
  }

  Affix.prototype.checkPosition = function () {
    if (!this.$element.is(':visible')) return

    var height       = this.$element.height()
    var offset       = this.options.offset
    var offsetTop    = offset.top
    var offsetBottom = offset.bottom
    var scrollHeight = Math.max($(document).height(), $(document.body).height())

    if (typeof offset != 'object')         offsetBottom = offsetTop = offset
    if (typeof offsetTop == 'function')    offsetTop    = offset.top(this.$element)
    if (typeof offsetBottom == 'function') offsetBottom = offset.bottom(this.$element)

    var affix = this.getState(scrollHeight, height, offsetTop, offsetBottom)

    if (this.affixed != affix) {
      if (this.unpin != null) this.$element.css('top', '')

      var affixType = 'affix' + (affix ? '-' + affix : '')
      var e         = $.Event(affixType + '.bs.affix')

      this.$element.trigger(e)

      if (e.isDefaultPrevented()) return

      this.affixed = affix
      this.unpin = affix == 'bottom' ? this.getPinnedOffset() : null

      this.$element
        .removeClass(Affix.RESET)
        .addClass(affixType)
        .trigger(affixType.replace('affix', 'affixed') + '.bs.affix')
    }

    if (affix == 'bottom') {
      this.$element.offset({
        top: scrollHeight - height - offsetBottom
      })
    }
  }


  // AFFIX PLUGIN DEFINITION
  // =======================

  function Plugin(option) {
    return this.each(function () {
      var $this   = $(this)
      var data    = $this.data('bs.affix')
      var options = typeof option == 'object' && option

      if (!data) $this.data('bs.affix', (data = new Affix(this, options)))
      if (typeof option == 'string') data[option]()
    })
  }

  var old = $.fn.affix

  $.fn.affix             = Plugin
  $.fn.affix.Constructor = Affix


  // AFFIX NO CONFLICT
  // =================

  $.fn.affix.noConflict = function () {
    $.fn.affix = old
    return this
  }


  // AFFIX DATA-API
  // ==============

  $(window).on('load', function () {
    $('[data-spy="affix"]').each(function () {
      var $spy = $(this)
      var data = $spy.data()

      data.offset = data.offset || {}

      if (data.offsetBottom != null) data.offset.bottom = data.offsetBottom
      if (data.offsetTop    != null) data.offset.top    = data.offsetTop

      Plugin.call($spy, data)
    })
  })

}(jQuery);
/* ========================================================================
 * Bootstrap: alert.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#alerts
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // ALERT CLASS DEFINITION
  // ======================

  var dismiss = '[data-dismiss="alert"]'
  var Alert   = function (el) {
    $(el).on('click', dismiss, this.close)
  }

  Alert.VERSION = '3.4.1'

  Alert.TRANSITION_DURATION = 150

  Alert.prototype.close = function (e) {
    var $this    = $(this)
    var selector = $this.attr('data-target')

    if (!selector) {
      selector = $this.attr('href')
      selector = selector && selector.replace(/.*(?=#[^\s]*$)/, '') // strip for ie7
    }

    selector    = selector === '#' ? [] : selector
    var $parent = $(document).find(selector)

    if (e) e.preventDefault()

    if (!$parent.length) {
      $parent = $this.closest('.alert')
    }

    $parent.trigger(e = $.Event('close.bs.alert'))

    if (e.isDefaultPrevented()) return

    $parent.removeClass('in')

    function removeElement() {
      // detach from parent, fire event then clean up data
      $parent.detach().trigger('closed.bs.alert').remove()
    }

    $.support.transition && $parent.hasClass('fade') ?
      $parent
        .one('bsTransitionEnd', removeElement)
        .emulateTransitionEnd(Alert.TRANSITION_DURATION) :
      removeElement()
  }


  // ALERT PLUGIN DEFINITION
  // =======================

  function Plugin(option) {
    return this.each(function () {
      var $this = $(this)
      var data  = $this.data('bs.alert')

      if (!data) $this.data('bs.alert', (data = new Alert(this)))
      if (typeof option == 'string') data[option].call($this)
    })
  }

  var old = $.fn.alert

  $.fn.alert             = Plugin
  $.fn.alert.Constructor = Alert


  // ALERT NO CONFLICT
  // =================

  $.fn.alert.noConflict = function () {
    $.fn.alert = old
    return this
  }


  // ALERT DATA-API
  // ==============

  $(document).on('click.bs.alert.data-api', dismiss, Alert.prototype.close)

}(jQuery);
/* ========================================================================
 * Bootstrap: button.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#buttons
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // BUTTON PUBLIC CLASS DEFINITION
  // ==============================

  var Button = function (element, options) {
    this.$element  = $(element)
    this.options   = $.extend({}, Button.DEFAULTS, options)
    this.isLoading = false
  }

  Button.VERSION  = '3.4.1'

  Button.DEFAULTS = {
    loadingText: 'loading...'
  }

  Button.prototype.setState = function (state) {
    var d    = 'disabled'
    var $el  = this.$element
    var val  = $el.is('input') ? 'val' : 'html'
    var data = $el.data()

    state += 'Text'

    if (data.resetText == null) $el.data('resetText', $el[val]())

    // push to event loop to allow forms to submit
    setTimeout($.proxy(function () {
      $el[val](data[state] == null ? this.options[state] : data[state])

      if (state == 'loadingText') {
        this.isLoading = true
        $el.addClass(d).attr(d, d).prop(d, true)
      } else if (this.isLoading) {
        this.isLoading = false
        $el.removeClass(d).removeAttr(d).prop(d, false)
      }
    }, this), 0)
  }

  Button.prototype.toggle = function () {
    var changed = true
    var $parent = this.$element.closest('[data-toggle="buttons"]')

    if ($parent.length) {
      var $input = this.$element.find('input')
      if ($input.prop('type') == 'radio') {
        if ($input.prop('checked')) changed = false
        $parent.find('.active').removeClass('active')
        this.$element.addClass('active')
      } else if ($input.prop('type') == 'checkbox') {
        if (($input.prop('checked')) !== this.$element.hasClass('active')) changed = false
        this.$element.toggleClass('active')
      }
      $input.prop('checked', this.$element.hasClass('active'))
      if (changed) $input.trigger('change')
    } else {
      this.$element.attr('aria-pressed', !this.$element.hasClass('active'))
      this.$element.toggleClass('active')
    }
  }


  // BUTTON PLUGIN DEFINITION
  // ========================

  function Plugin(option) {
    return this.each(function () {
      var $this   = $(this)
      var data    = $this.data('bs.button')
      var options = typeof option == 'object' && option

      if (!data) $this.data('bs.button', (data = new Button(this, options)))

      if (option == 'toggle') data.toggle()
      else if (option) data.setState(option)
    })
  }

  var old = $.fn.button

  $.fn.button             = Plugin
  $.fn.button.Constructor = Button


  // BUTTON NO CONFLICT
  // ==================

  $.fn.button.noConflict = function () {
    $.fn.button = old
    return this
  }


  // BUTTON DATA-API
  // ===============

  $(document)
    .on('click.bs.button.data-api', '[data-toggle^="button"]', function (e) {
      var $btn = $(e.target).closest('.btn')
      Plugin.call($btn, 'toggle')
      if (!($(e.target).is('input[type="radio"], input[type="checkbox"]'))) {
        // Prevent double click on radios, and the double selections (so cancellation) on checkboxes
        e.preventDefault()
        // The target component still receive the focus
        if ($btn.is('input,button')) $btn.trigger('focus')
        else $btn.find('input:visible,button:visible').first().trigger('focus')
      }
    })
    .on('focus.bs.button.data-api blur.bs.button.data-api', '[data-toggle^="button"]', function (e) {
      $(e.target).closest('.btn').toggleClass('focus', /^focus(in)?$/.test(e.type))
    })

}(jQuery);
/* ========================================================================
 * Bootstrap: carousel.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#carousel
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // CAROUSEL CLASS DEFINITION
  // =========================

  var Carousel = function (element, options) {
    this.$element    = $(element)
    this.$indicators = this.$element.find('.carousel-indicators')
    this.options     = options
    this.paused      = null
    this.sliding     = null
    this.interval    = null
    this.$active     = null
    this.$items      = null

    this.options.keyboard && this.$element.on('keydown.bs.carousel', $.proxy(this.keydown, this))

    this.options.pause == 'hover' && !('ontouchstart' in document.documentElement) && this.$element
      .on('mouseenter.bs.carousel', $.proxy(this.pause, this))
      .on('mouseleave.bs.carousel', $.proxy(this.cycle, this))
  }

  Carousel.VERSION  = '3.4.1'

  Carousel.TRANSITION_DURATION = 600

  Carousel.DEFAULTS = {
    interval: 5000,
    pause: 'hover',
    wrap: true,
    keyboard: true
  }

  Carousel.prototype.keydown = function (e) {
    if (/input|textarea/i.test(e.target.tagName)) return
    switch (e.which) {
      case 37: this.prev(); break
      case 39: this.next(); break
      default: return
    }

    e.preventDefault()
  }

  Carousel.prototype.cycle = function (e) {
    e || (this.paused = false)

    this.interval && clearInterval(this.interval)

    this.options.interval
      && !this.paused
      && (this.interval = setInterval($.proxy(this.next, this), this.options.interval))

    return this
  }

  Carousel.prototype.getItemIndex = function (item) {
    this.$items = item.parent().children('.item')
    return this.$items.index(item || this.$active)
  }

  Carousel.prototype.getItemForDirection = function (direction, active) {
    var activeIndex = this.getItemIndex(active)
    var willWrap = (direction == 'prev' && activeIndex === 0)
                || (direction == 'next' && activeIndex == (this.$items.length - 1))
    if (willWrap && !this.options.wrap) return active
    var delta = direction == 'prev' ? -1 : 1
    var itemIndex = (activeIndex + delta) % this.$items.length
    return this.$items.eq(itemIndex)
  }

  Carousel.prototype.to = function (pos) {
    var that        = this
    var activeIndex = this.getItemIndex(this.$active = this.$element.find('.item.active'))

    if (pos > (this.$items.length - 1) || pos < 0) return

    if (this.sliding)       return this.$element.one('slid.bs.carousel', function () { that.to(pos) }) // yes, "slid"
    if (activeIndex == pos) return this.pause().cycle()

    return this.slide(pos > activeIndex ? 'next' : 'prev', this.$items.eq(pos))
  }

  Carousel.prototype.pause = function (e) {
    e || (this.paused = true)

    if (this.$element.find('.next, .prev').length && $.support.transition) {
      this.$element.trigger($.support.transition.end)
      this.cycle(true)
    }

    this.interval = clearInterval(this.interval)

    return this
  }

  Carousel.prototype.next = function () {
    if (this.sliding) return
    return this.slide('next')
  }

  Carousel.prototype.prev = function () {
    if (this.sliding) return
    return this.slide('prev')
  }

  Carousel.prototype.slide = function (type, next) {
    var $active   = this.$element.find('.item.active')
    var $next     = next || this.getItemForDirection(type, $active)
    var isCycling = this.interval
    var direction = type == 'next' ? 'left' : 'right'
    var that      = this

    if ($next.hasClass('active')) return (this.sliding = false)

    var relatedTarget = $next[0]
    var slideEvent = $.Event('slide.bs.carousel', {
      relatedTarget: relatedTarget,
      direction: direction
    })
    this.$element.trigger(slideEvent)
    if (slideEvent.isDefaultPrevented()) return

    this.sliding = true

    isCycling && this.pause()

    if (this.$indicators.length) {
      this.$indicators.find('.active').removeClass('active')
      var $nextIndicator = $(this.$indicators.children()[this.getItemIndex($next)])
      $nextIndicator && $nextIndicator.addClass('active')
    }

    var slidEvent = $.Event('slid.bs.carousel', { relatedTarget: relatedTarget, direction: direction }) // yes, "slid"
    if ($.support.transition && this.$element.hasClass('slide')) {
      $next.addClass(type)
      if (typeof $next === 'object' && $next.length) {
        $next[0].offsetWidth // force reflow
      }
      $active.addClass(direction)
      $next.addClass(direction)
      $active
        .one('bsTransitionEnd', function () {
          $next.removeClass([type, direction].join(' ')).addClass('active')
          $active.removeClass(['active', direction].join(' '))
          that.sliding = false
          setTimeout(function () {
            that.$element.trigger(slidEvent)
          }, 0)
        })
        .emulateTransitionEnd(Carousel.TRANSITION_DURATION)
    } else {
      $active.removeClass('active')
      $next.addClass('active')
      this.sliding = false
      this.$element.trigger(slidEvent)
    }

    isCycling && this.cycle()

    return this
  }


  // CAROUSEL PLUGIN DEFINITION
  // ==========================

  function Plugin(option) {
    return this.each(function () {
      var $this   = $(this)
      var data    = $this.data('bs.carousel')
      var options = $.extend({}, Carousel.DEFAULTS, $this.data(), typeof option == 'object' && option)
      var action  = typeof option == 'string' ? option : options.slide

      if (!data) $this.data('bs.carousel', (data = new Carousel(this, options)))
      if (typeof option == 'number') data.to(option)
      else if (action) data[action]()
      else if (options.interval) data.pause().cycle()
    })
  }

  var old = $.fn.carousel

  $.fn.carousel             = Plugin
  $.fn.carousel.Constructor = Carousel


  // CAROUSEL NO CONFLICT
  // ====================

  $.fn.carousel.noConflict = function () {
    $.fn.carousel = old
    return this
  }


  // CAROUSEL DATA-API
  // =================

  var clickHandler = function (e) {
    var $this   = $(this)
    var href    = $this.attr('href')
    if (href) {
      href = href.replace(/.*(?=#[^\s]+$)/, '') // strip for ie7
    }

    var target  = $this.attr('data-target') || href
    var $target = $(document).find(target)

    if (!$target.hasClass('carousel')) return

    var options = $.extend({}, $target.data(), $this.data())
    var slideIndex = $this.attr('data-slide-to')
    if (slideIndex) options.interval = false

    Plugin.call($target, options)

    if (slideIndex) {
      $target.data('bs.carousel').to(slideIndex)
    }

    e.preventDefault()
  }

  $(document)
    .on('click.bs.carousel.data-api', '[data-slide]', clickHandler)
    .on('click.bs.carousel.data-api', '[data-slide-to]', clickHandler)

  $(window).on('load', function () {
    $('[data-ride="carousel"]').each(function () {
      var $carousel = $(this)
      Plugin.call($carousel, $carousel.data())
    })
  })

}(jQuery);
/* ========================================================================
 * Bootstrap: collapse.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#collapse
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */

/* jshint latedef: false */

+function ($) {
  'use strict';

  // COLLAPSE PUBLIC CLASS DEFINITION
  // ================================

  var Collapse = function (element, options) {
    this.$element      = $(element)
    this.options       = $.extend({}, Collapse.DEFAULTS, options)
    this.$trigger      = $('[data-toggle="collapse"][href="#' + element.id + '"],' +
                           '[data-toggle="collapse"][data-target="#' + element.id + '"]')
    this.transitioning = null

    if (this.options.parent) {
      this.$parent = this.getParent()
    } else {
      this.addAriaAndCollapsedClass(this.$element, this.$trigger)
    }

    if (this.options.toggle) this.toggle()
  }

  Collapse.VERSION  = '3.4.1'

  Collapse.TRANSITION_DURATION = 350

  Collapse.DEFAULTS = {
    toggle: true
  }

  Collapse.prototype.dimension = function () {
    var hasWidth = this.$element.hasClass('width')
    return hasWidth ? 'width' : 'height'
  }

  Collapse.prototype.show = function () {
    if (this.transitioning || this.$element.hasClass('in')) return

    var activesData
    var actives = this.$parent && this.$parent.children('.panel').children('.in, .collapsing')

    if (actives && actives.length) {
      activesData = actives.data('bs.collapse')
      if (activesData && activesData.transitioning) return
    }

    var startEvent = $.Event('show.bs.collapse')
    this.$element.trigger(startEvent)
    if (startEvent.isDefaultPrevented()) return

    if (actives && actives.length) {
      Plugin.call(actives, 'hide')
      activesData || actives.data('bs.collapse', null)
    }

    var dimension = this.dimension()

    this.$element
      .removeClass('collapse')
      .addClass('collapsing')[dimension](0)
      .attr('aria-expanded', true)

    this.$trigger
      .removeClass('collapsed')
      .attr('aria-expanded', true)

    this.transitioning = 1

    var complete = function () {
      this.$element
        .removeClass('collapsing')
        .addClass('collapse in')[dimension]('')
      this.transitioning = 0
      this.$element
        .trigger('shown.bs.collapse')
    }

    if (!$.support.transition) return complete.call(this)

    var scrollSize = $.camelCase(['scroll', dimension].join('-'))

    this.$element
      .one('bsTransitionEnd', $.proxy(complete, this))
      .emulateTransitionEnd(Collapse.TRANSITION_DURATION)[dimension](this.$element[0][scrollSize])
  }

  Collapse.prototype.hide = function () {
    if (this.transitioning || !this.$element.hasClass('in')) return

    var startEvent = $.Event('hide.bs.collapse')
    this.$element.trigger(startEvent)
    if (startEvent.isDefaultPrevented()) return

    var dimension = this.dimension()

    this.$element[dimension](this.$element[dimension]())[0].offsetHeight

    this.$element
      .addClass('collapsing')
      .removeClass('collapse in')
      .attr('aria-expanded', false)

    this.$trigger
      .addClass('collapsed')
      .attr('aria-expanded', false)

    this.transitioning = 1

    var complete = function () {
      this.transitioning = 0
      this.$element
        .removeClass('collapsing')
        .addClass('collapse')
        .trigger('hidden.bs.collapse')
    }

    if (!$.support.transition) return complete.call(this)

    this.$element
      [dimension](0)
      .one('bsTransitionEnd', $.proxy(complete, this))
      .emulateTransitionEnd(Collapse.TRANSITION_DURATION)
  }

  Collapse.prototype.toggle = function () {
    this[this.$element.hasClass('in') ? 'hide' : 'show']()
  }

  Collapse.prototype.getParent = function () {
    return $(document).find(this.options.parent)
      .find('[data-toggle="collapse"][data-parent="' + this.options.parent + '"]')
      .each($.proxy(function (i, element) {
        var $element = $(element)
        this.addAriaAndCollapsedClass(getTargetFromTrigger($element), $element)
      }, this))
      .end()
  }

  Collapse.prototype.addAriaAndCollapsedClass = function ($element, $trigger) {
    var isOpen = $element.hasClass('in')

    $element.attr('aria-expanded', isOpen)
    $trigger
      .toggleClass('collapsed', !isOpen)
      .attr('aria-expanded', isOpen)
  }

  function getTargetFromTrigger($trigger) {
    var href
    var target = $trigger.attr('data-target')
      || (href = $trigger.attr('href')) && href.replace(/.*(?=#[^\s]+$)/, '') // strip for ie7

    return $(document).find(target)
  }


  // COLLAPSE PLUGIN DEFINITION
  // ==========================

  function Plugin(option) {
    return this.each(function () {
      var $this   = $(this)
      var data    = $this.data('bs.collapse')
      var options = $.extend({}, Collapse.DEFAULTS, $this.data(), typeof option == 'object' && option)

      if (!data && options.toggle && /show|hide/.test(option)) options.toggle = false
      if (!data) $this.data('bs.collapse', (data = new Collapse(this, options)))
      if (typeof option == 'string') data[option]()
    })
  }

  var old = $.fn.collapse

  $.fn.collapse             = Plugin
  $.fn.collapse.Constructor = Collapse


  // COLLAPSE NO CONFLICT
  // ====================

  $.fn.collapse.noConflict = function () {
    $.fn.collapse = old
    return this
  }


  // COLLAPSE DATA-API
  // =================

  $(document).on('click.bs.collapse.data-api', '[data-toggle="collapse"]', function (e) {
    var $this   = $(this)

    if (!$this.attr('data-target')) e.preventDefault()

    var $target = getTargetFromTrigger($this)
    var data    = $target.data('bs.collapse')
    var option  = data ? 'toggle' : $this.data()

    Plugin.call($target, option)
  })

}(jQuery);
/* ========================================================================
 * Bootstrap: dropdown.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#dropdowns
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // DROPDOWN CLASS DEFINITION
  // =========================

  var backdrop = '.dropdown-backdrop'
  var toggle   = '[data-toggle="dropdown"]'
  var Dropdown = function (element) {
    $(element).on('click.bs.dropdown', this.toggle)
  }

  Dropdown.VERSION = '3.4.1'

  function getParent($this) {
    var selector = $this.attr('data-target')

    if (!selector) {
      selector = $this.attr('href')
      selector = selector && /#[A-Za-z]/.test(selector) && selector.replace(/.*(?=#[^\s]*$)/, '') // strip for ie7
    }

    var $parent = selector !== '#' ? $(document).find(selector) : null

    return $parent && $parent.length ? $parent : $this.parent()
  }

  function clearMenus(e) {
    if (e && e.which === 3) return
    $(backdrop).remove()
    $(toggle).each(function () {
      var $this         = $(this)
      var $parent       = getParent($this)
      var relatedTarget = { relatedTarget: this }

      if (!$parent.hasClass('open')) return

      if (e && e.type == 'click' && /input|textarea/i.test(e.target.tagName) && $.contains($parent[0], e.target)) return

      $parent.trigger(e = $.Event('hide.bs.dropdown', relatedTarget))

      if (e.isDefaultPrevented()) return

      $this.attr('aria-expanded', 'false')
      $parent.removeClass('open').trigger($.Event('hidden.bs.dropdown', relatedTarget))
    })
  }

  Dropdown.prototype.toggle = function (e) {
    var $this = $(this)

    if ($this.is('.disabled, :disabled')) return

    var $parent  = getParent($this)
    var isActive = $parent.hasClass('open')

    clearMenus()

    if (!isActive) {
      if ('ontouchstart' in document.documentElement && !$parent.closest('.navbar-nav').length) {
        // if mobile we use a backdrop because click events don't delegate
        $(document.createElement('div'))
          .addClass('dropdown-backdrop')
          .insertAfter($(this))
          .on('click', clearMenus)
      }

      var relatedTarget = { relatedTarget: this }
      $parent.trigger(e = $.Event('show.bs.dropdown', relatedTarget))

      if (e.isDefaultPrevented()) return

      $this
        .trigger('focus')
        .attr('aria-expanded', 'true')

      $parent
        .toggleClass('open')
        .trigger($.Event('shown.bs.dropdown', relatedTarget))
    }

    return false
  }

  Dropdown.prototype.keydown = function (e) {
    if (!/(38|40|27|32)/.test(e.which) || /input|textarea/i.test(e.target.tagName)) return

    var $this = $(this)

    e.preventDefault()
    e.stopPropagation()

    if ($this.is('.disabled, :disabled')) return

    var $parent  = getParent($this)
    var isActive = $parent.hasClass('open')

    if (!isActive && e.which != 27 || isActive && e.which == 27) {
      if (e.which == 27) $parent.find(toggle).trigger('focus')
      return $this.trigger('click')
    }

    var desc = ' li:not(.disabled):visible a'
    var $items = $parent.find('.dropdown-menu' + desc)

    if (!$items.length) return

    var index = $items.index(e.target)

    if (e.which == 38 && index > 0)                 index--         // up
    if (e.which == 40 && index < $items.length - 1) index++         // down
    if (!~index)                                    index = 0

    $items.eq(index).trigger('focus')
  }


  // DROPDOWN PLUGIN DEFINITION
  // ==========================

  function Plugin(option) {
    return this.each(function () {
      var $this = $(this)
      var data  = $this.data('bs.dropdown')

      if (!data) $this.data('bs.dropdown', (data = new Dropdown(this)))
      if (typeof option == 'string') data[option].call($this)
    })
  }

  var old = $.fn.dropdown

  $.fn.dropdown             = Plugin
  $.fn.dropdown.Constructor = Dropdown


  // DROPDOWN NO CONFLICT
  // ====================

  $.fn.dropdown.noConflict = function () {
    $.fn.dropdown = old
    return this
  }


  // APPLY TO STANDARD DROPDOWN ELEMENTS
  // ===================================

  $(document)
    .on('click.bs.dropdown.data-api', clearMenus)
    .on('click.bs.dropdown.data-api', '.dropdown form', function (e) { e.stopPropagation() })
    .on('click.bs.dropdown.data-api', toggle, Dropdown.prototype.toggle)
    .on('keydown.bs.dropdown.data-api', toggle, Dropdown.prototype.keydown)
    .on('keydown.bs.dropdown.data-api', '.dropdown-menu', Dropdown.prototype.keydown)

}(jQuery);
/* ========================================================================
 * Bootstrap: modal.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#modals
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // MODAL CLASS DEFINITION
  // ======================

  var Modal = function (element, options) {
    this.options = options
    this.$body = $(document.body)
    this.$element = $(element)
    this.$dialog = this.$element.find('.modal-dialog')
    this.$backdrop = null
    this.isShown = null
    this.originalBodyPad = null
    this.scrollbarWidth = 0
    this.ignoreBackdropClick = false
    this.fixedContent = '.navbar-fixed-top, .navbar-fixed-bottom'

    if (this.options.remote) {
      this.$element
        .find('.modal-content')
        .load(this.options.remote, $.proxy(function () {
          this.$element.trigger('loaded.bs.modal')
        }, this))
    }
  }

  Modal.VERSION = '3.4.1'

  Modal.TRANSITION_DURATION = 300
  Modal.BACKDROP_TRANSITION_DURATION = 150

  Modal.DEFAULTS = {
    backdrop: true,
    keyboard: true,
    show: true
  }

  Modal.prototype.toggle = function (_relatedTarget) {
    return this.isShown ? this.hide() : this.show(_relatedTarget)
  }

  Modal.prototype.show = function (_relatedTarget) {
    var that = this
    var e = $.Event('show.bs.modal', { relatedTarget: _relatedTarget })

    this.$element.trigger(e)

    if (this.isShown || e.isDefaultPrevented()) return

    this.isShown = true

    this.checkScrollbar()
    this.setScrollbar()
    this.$body.addClass('modal-open')

    this.escape()
    this.resize()

    this.$element.on('click.dismiss.bs.modal', '[data-dismiss="modal"]', $.proxy(this.hide, this))

    this.$dialog.on('mousedown.dismiss.bs.modal', function () {
      that.$element.one('mouseup.dismiss.bs.modal', function (e) {
        if ($(e.target).is(that.$element)) that.ignoreBackdropClick = true
      })
    })

    this.backdrop(function () {
      var transition = $.support.transition && that.$element.hasClass('fade')

      if (!that.$element.parent().length) {
        that.$element.appendTo(that.$body) // don't move modals dom position
      }

      that.$element
        .show()
        .scrollTop(0)

      that.adjustDialog()

      if (transition) {
        that.$element[0].offsetWidth // force reflow
      }

      that.$element.addClass('in')

      that.enforceFocus()

      var e = $.Event('shown.bs.modal', { relatedTarget: _relatedTarget })

      transition ?
        that.$dialog // wait for modal to slide in
          .one('bsTransitionEnd', function () {
            that.$element.trigger('focus').trigger(e)
          })
          .emulateTransitionEnd(Modal.TRANSITION_DURATION) :
        that.$element.trigger('focus').trigger(e)
    })
  }

  Modal.prototype.hide = function (e) {
    if (e) e.preventDefault()

    e = $.Event('hide.bs.modal')

    this.$element.trigger(e)

    if (!this.isShown || e.isDefaultPrevented()) return

    this.isShown = false

    this.escape()
    this.resize()

    $(document).off('focusin.bs.modal')

    this.$element
      .removeClass('in')
      .off('click.dismiss.bs.modal')
      .off('mouseup.dismiss.bs.modal')

    this.$dialog.off('mousedown.dismiss.bs.modal')

    $.support.transition && this.$element.hasClass('fade') ?
      this.$element
        .one('bsTransitionEnd', $.proxy(this.hideModal, this))
        .emulateTransitionEnd(Modal.TRANSITION_DURATION) :
      this.hideModal()
  }

  Modal.prototype.enforceFocus = function () {
    $(document)
      .off('focusin.bs.modal') // guard against infinite focus loop
      .on('focusin.bs.modal', $.proxy(function (e) {
        if (document !== e.target &&
          this.$element[0] !== e.target &&
          !this.$element.has(e.target).length) {
          this.$element.trigger('focus')
        }
      }, this))
  }

  Modal.prototype.escape = function () {
    if (this.isShown && this.options.keyboard) {
      this.$element.on('keydown.dismiss.bs.modal', $.proxy(function (e) {
        e.which == 27 && this.hide()
      }, this))
    } else if (!this.isShown) {
      this.$element.off('keydown.dismiss.bs.modal')
    }
  }

  Modal.prototype.resize = function () {
    if (this.isShown) {
      $(window).on('resize.bs.modal', $.proxy(this.handleUpdate, this))
    } else {
      $(window).off('resize.bs.modal')
    }
  }

  Modal.prototype.hideModal = function () {
    var that = this
    this.$element.hide()
    this.backdrop(function () {
      that.$body.removeClass('modal-open')
      that.resetAdjustments()
      that.resetScrollbar()
      that.$element.trigger('hidden.bs.modal')
    })
  }

  Modal.prototype.removeBackdrop = function () {
    this.$backdrop && this.$backdrop.remove()
    this.$backdrop = null
  }

  Modal.prototype.backdrop = function (callback) {
    var that = this
    var animate = this.$element.hasClass('fade') ? 'fade' : ''

    if (this.isShown && this.options.backdrop) {
      var doAnimate = $.support.transition && animate

      this.$backdrop = $(document.createElement('div'))
        .addClass('modal-backdrop ' + animate)
        .appendTo(this.$body)

      this.$element.on('click.dismiss.bs.modal', $.proxy(function (e) {
        if (this.ignoreBackdropClick) {
          this.ignoreBackdropClick = false
          return
        }
        if (e.target !== e.currentTarget) return
        this.options.backdrop == 'static'
          ? this.$element[0].focus()
          : this.hide()
      }, this))

      if (doAnimate) this.$backdrop[0].offsetWidth // force reflow

      this.$backdrop.addClass('in')

      if (!callback) return

      doAnimate ?
        this.$backdrop
          .one('bsTransitionEnd', callback)
          .emulateTransitionEnd(Modal.BACKDROP_TRANSITION_DURATION) :
        callback()

    } else if (!this.isShown && this.$backdrop) {
      this.$backdrop.removeClass('in')

      var callbackRemove = function () {
        that.removeBackdrop()
        callback && callback()
      }
      $.support.transition && this.$element.hasClass('fade') ?
        this.$backdrop
          .one('bsTransitionEnd', callbackRemove)
          .emulateTransitionEnd(Modal.BACKDROP_TRANSITION_DURATION) :
        callbackRemove()

    } else if (callback) {
      callback()
    }
  }

  // these following methods are used to handle overflowing modals

  Modal.prototype.handleUpdate = function () {
    this.adjustDialog()
  }

  Modal.prototype.adjustDialog = function () {
    var modalIsOverflowing = this.$element[0].scrollHeight > document.documentElement.clientHeight

    this.$element.css({
      paddingLeft: !this.bodyIsOverflowing && modalIsOverflowing ? this.scrollbarWidth : '',
      paddingRight: this.bodyIsOverflowing && !modalIsOverflowing ? this.scrollbarWidth : ''
    })
  }

  Modal.prototype.resetAdjustments = function () {
    this.$element.css({
      paddingLeft: '',
      paddingRight: ''
    })
  }

  Modal.prototype.checkScrollbar = function () {
    var fullWindowWidth = window.innerWidth
    if (!fullWindowWidth) { // workaround for missing window.innerWidth in IE8
      var documentElementRect = document.documentElement.getBoundingClientRect()
      fullWindowWidth = documentElementRect.right - Math.abs(documentElementRect.left)
    }
    this.bodyIsOverflowing = document.body.clientWidth < fullWindowWidth
    this.scrollbarWidth = this.measureScrollbar()
  }

  Modal.prototype.setScrollbar = function () {
    var bodyPad = parseInt((this.$body.css('padding-right') || 0), 10)
    this.originalBodyPad = document.body.style.paddingRight || ''
    var scrollbarWidth = this.scrollbarWidth
    if (this.bodyIsOverflowing) {
      this.$body.css('padding-right', bodyPad + scrollbarWidth)
      $(this.fixedContent).each(function (index, element) {
        var actualPadding = element.style.paddingRight
        var calculatedPadding = $(element).css('padding-right')
        $(element)
          .data('padding-right', actualPadding)
          .css('padding-right', parseFloat(calculatedPadding) + scrollbarWidth + 'px')
      })
    }
  }

  Modal.prototype.resetScrollbar = function () {
    this.$body.css('padding-right', this.originalBodyPad)
    $(this.fixedContent).each(function (index, element) {
      var padding = $(element).data('padding-right')
      $(element).removeData('padding-right')
      element.style.paddingRight = padding ? padding : ''
    })
  }

  Modal.prototype.measureScrollbar = function () { // thx walsh
    var scrollDiv = document.createElement('div')
    scrollDiv.className = 'modal-scrollbar-measure'
    this.$body.append(scrollDiv)
    var scrollbarWidth = scrollDiv.offsetWidth - scrollDiv.clientWidth
    this.$body[0].removeChild(scrollDiv)
    return scrollbarWidth
  }


  // MODAL PLUGIN DEFINITION
  // =======================

  function Plugin(option, _relatedTarget) {
    return this.each(function () {
      var $this = $(this)
      var data = $this.data('bs.modal')
      var options = $.extend({}, Modal.DEFAULTS, $this.data(), typeof option == 'object' && option)

      if (!data) $this.data('bs.modal', (data = new Modal(this, options)))
      if (typeof option == 'string') data[option](_relatedTarget)
      else if (options.show) data.show(_relatedTarget)
    })
  }

  var old = $.fn.modal

  $.fn.modal = Plugin
  $.fn.modal.Constructor = Modal


  // MODAL NO CONFLICT
  // =================

  $.fn.modal.noConflict = function () {
    $.fn.modal = old
    return this
  }


  // MODAL DATA-API
  // ==============

  $(document).on('click.bs.modal.data-api', '[data-toggle="modal"]', function (e) {
    var $this = $(this)
    var href = $this.attr('href')
    var target = $this.attr('data-target') ||
      (href && href.replace(/.*(?=#[^\s]+$)/, '')) // strip for ie7

    var $target = $(document).find(target)
    var option = $target.data('bs.modal') ? 'toggle' : $.extend({ remote: !/#/.test(href) && href }, $target.data(), $this.data())

    if ($this.is('a')) e.preventDefault()

    $target.one('show.bs.modal', function (showEvent) {
      if (showEvent.isDefaultPrevented()) return // only register focus restorer if modal will actually get shown
      $target.one('hidden.bs.modal', function () {
        $this.is(':visible') && $this.trigger('focus')
      })
    })
    Plugin.call($target, option, this)
  })

}(jQuery);
/* ========================================================================
 * Bootstrap: scrollspy.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#scrollspy
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // SCROLLSPY CLASS DEFINITION
  // ==========================

  function ScrollSpy(element, options) {
    this.$body          = $(document.body)
    this.$scrollElement = $(element).is(document.body) ? $(window) : $(element)
    this.options        = $.extend({}, ScrollSpy.DEFAULTS, options)
    this.selector       = (this.options.target || '') + ' .nav li > a'
    this.offsets        = []
    this.targets        = []
    this.activeTarget   = null
    this.scrollHeight   = 0

    this.$scrollElement.on('scroll.bs.scrollspy', $.proxy(this.process, this))
    this.refresh()
    this.process()
  }

  ScrollSpy.VERSION  = '3.4.1'

  ScrollSpy.DEFAULTS = {
    offset: 10
  }

  ScrollSpy.prototype.getScrollHeight = function () {
    return this.$scrollElement[0].scrollHeight || Math.max(this.$body[0].scrollHeight, document.documentElement.scrollHeight)
  }

  ScrollSpy.prototype.refresh = function () {
    var that          = this
    var offsetMethod  = 'offset'
    var offsetBase    = 0

    this.offsets      = []
    this.targets      = []
    this.scrollHeight = this.getScrollHeight()

    if (!$.isWindow(this.$scrollElement[0])) {
      offsetMethod = 'position'
      offsetBase   = this.$scrollElement.scrollTop()
    }

    this.$body
      .find(this.selector)
      .map(function () {
        var $el   = $(this)
        var href  = $el.data('target') || $el.attr('href')
        var $href = /^#./.test(href) && $(href)

        return ($href
          && $href.length
          && $href.is(':visible')
          && [[$href[offsetMethod]().top + offsetBase, href]]) || null
      })
      .sort(function (a, b) { return a[0] - b[0] })
      .each(function () {
        that.offsets.push(this[0])
        that.targets.push(this[1])
      })
  }

  ScrollSpy.prototype.process = function () {
    var scrollTop    = this.$scrollElement.scrollTop() + this.options.offset
    var scrollHeight = this.getScrollHeight()
    var maxScroll    = this.options.offset + scrollHeight - this.$scrollElement.height()
    var offsets      = this.offsets
    var targets      = this.targets
    var activeTarget = this.activeTarget
    var i

    if (this.scrollHeight != scrollHeight) {
      this.refresh()
    }

    if (scrollTop >= maxScroll) {
      return activeTarget != (i = targets[targets.length - 1]) && this.activate(i)
    }

    if (activeTarget && scrollTop < offsets[0]) {
      this.activeTarget = null
      return this.clear()
    }

    for (i = offsets.length; i--;) {
      activeTarget != targets[i]
        && scrollTop >= offsets[i]
        && (offsets[i + 1] === undefined || scrollTop < offsets[i + 1])
        && this.activate(targets[i])
    }
  }

  ScrollSpy.prototype.activate = function (target) {
    this.activeTarget = target

    this.clear()

    var selector = this.selector +
      '[data-target="' + target + '"],' +
      this.selector + '[href="' + target + '"]'

    var active = $(selector)
      .parents('li')
      .addClass('active')

    if (active.parent('.dropdown-menu').length) {
      active = active
        .closest('li.dropdown')
        .addClass('active')
    }

    active.trigger('activate.bs.scrollspy')
  }

  ScrollSpy.prototype.clear = function () {
    $(this.selector)
      .parentsUntil(this.options.target, '.active')
      .removeClass('active')
  }


  // SCROLLSPY PLUGIN DEFINITION
  // ===========================

  function Plugin(option) {
    return this.each(function () {
      var $this   = $(this)
      var data    = $this.data('bs.scrollspy')
      var options = typeof option == 'object' && option

      if (!data) $this.data('bs.scrollspy', (data = new ScrollSpy(this, options)))
      if (typeof option == 'string') data[option]()
    })
  }

  var old = $.fn.scrollspy

  $.fn.scrollspy             = Plugin
  $.fn.scrollspy.Constructor = ScrollSpy


  // SCROLLSPY NO CONFLICT
  // =====================

  $.fn.scrollspy.noConflict = function () {
    $.fn.scrollspy = old
    return this
  }


  // SCROLLSPY DATA-API
  // ==================

  $(window).on('load.bs.scrollspy.data-api', function () {
    $('[data-spy="scroll"]').each(function () {
      var $spy = $(this)
      Plugin.call($spy, $spy.data())
    })
  })

}(jQuery);
/* ========================================================================
 * Bootstrap: tab.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#tabs
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // TAB CLASS DEFINITION
  // ====================

  var Tab = function (element) {
    // jscs:disable requireDollarBeforejQueryAssignment
    this.element = $(element)
    // jscs:enable requireDollarBeforejQueryAssignment
  }

  Tab.VERSION = '3.4.1'

  Tab.TRANSITION_DURATION = 150

  Tab.prototype.show = function () {
    var $this    = this.element
    var $ul      = $this.closest('ul:not(.dropdown-menu)')
    var selector = $this.data('target')

    if (!selector) {
      selector = $this.attr('href')
      selector = selector && selector.replace(/.*(?=#[^\s]*$)/, '') // strip for ie7
    }

    if ($this.parent('li').hasClass('active')) return

    var $previous = $ul.find('.active:last a')
    var hideEvent = $.Event('hide.bs.tab', {
      relatedTarget: $this[0]
    })
    var showEvent = $.Event('show.bs.tab', {
      relatedTarget: $previous[0]
    })

    $previous.trigger(hideEvent)
    $this.trigger(showEvent)

    if (showEvent.isDefaultPrevented() || hideEvent.isDefaultPrevented()) return

    var $target = $(document).find(selector)

    this.activate($this.closest('li'), $ul)
    this.activate($target, $target.parent(), function () {
      $previous.trigger({
        type: 'hidden.bs.tab',
        relatedTarget: $this[0]
      })
      $this.trigger({
        type: 'shown.bs.tab',
        relatedTarget: $previous[0]
      })
    })
  }

  Tab.prototype.activate = function (element, container, callback) {
    var $active    = container.find('> .active')
    var transition = callback
      && $.support.transition
      && ($active.length && $active.hasClass('fade') || !!container.find('> .fade').length)

    function next() {
      $active
        .removeClass('active')
        .find('> .dropdown-menu > .active')
        .removeClass('active')
        .end()
        .find('[data-toggle="tab"]')
        .attr('aria-expanded', false)

      element
        .addClass('active')
        .find('[data-toggle="tab"]')
        .attr('aria-expanded', true)

      if (transition) {
        element[0].offsetWidth // reflow for transition
        element.addClass('in')
      } else {
        element.removeClass('fade')
      }

      if (element.parent('.dropdown-menu').length) {
        element
          .closest('li.dropdown')
          .addClass('active')
          .end()
          .find('[data-toggle="tab"]')
          .attr('aria-expanded', true)
      }

      callback && callback()
    }

    $active.length && transition ?
      $active
        .one('bsTransitionEnd', next)
        .emulateTransitionEnd(Tab.TRANSITION_DURATION) :
      next()

    $active.removeClass('in')
  }


  // TAB PLUGIN DEFINITION
  // =====================

  function Plugin(option) {
    return this.each(function () {
      var $this = $(this)
      var data  = $this.data('bs.tab')

      if (!data) $this.data('bs.tab', (data = new Tab(this)))
      if (typeof option == 'string') data[option]()
    })
  }

  var old = $.fn.tab

  $.fn.tab             = Plugin
  $.fn.tab.Constructor = Tab


  // TAB NO CONFLICT
  // ===============

  $.fn.tab.noConflict = function () {
    $.fn.tab = old
    return this
  }


  // TAB DATA-API
  // ============

  var clickHandler = function (e) {
    e.preventDefault()
    Plugin.call($(this), 'show')
  }

  $(document)
    .on('click.bs.tab.data-api', '[data-toggle="tab"]', clickHandler)
    .on('click.bs.tab.data-api', '[data-toggle="pill"]', clickHandler)

}(jQuery);
/* ========================================================================
 * Bootstrap: transition.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#transitions
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // CSS TRANSITION SUPPORT (Shoutout: https://modernizr.com/)
  // ============================================================

  function transitionEnd() {
    var el = document.createElement('bootstrap')

    var transEndEventNames = {
      WebkitTransition : 'webkitTransitionEnd',
      MozTransition    : 'transitionend',
      OTransition      : 'oTransitionEnd otransitionend',
      transition       : 'transitionend'
    }

    for (var name in transEndEventNames) {
      if (el.style[name] !== undefined) {
        return { end: transEndEventNames[name] }
      }
    }

    return false // explicit for ie8 (  ._.)
  }

  // https://blog.alexmaccaw.com/css-transitions
  $.fn.emulateTransitionEnd = function (duration) {
    var called = false
    var $el = this
    $(this).one('bsTransitionEnd', function () { called = true })
    var callback = function () { if (!called) $($el).trigger($.support.transition.end) }
    setTimeout(callback, duration)
    return this
  }

  $(function () {
    $.support.transition = transitionEnd()

    if (!$.support.transition) return

    $.event.special.bsTransitionEnd = {
      bindType: $.support.transition.end,
      delegateType: $.support.transition.end,
      handle: function (e) {
        if ($(e.target).is(this)) return e.handleObj.handler.apply(this, arguments)
      }
    }
  })

}(jQuery);
/* ========================================================================
 * Bootstrap: tooltip.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#tooltip
 * Inspired by the original jQuery.tipsy by Jason Frame
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */

+function ($) {
  'use strict';

  var DISALLOWED_ATTRIBUTES = ['sanitize', 'whiteList', 'sanitizeFn']

  var uriAttrs = [
    'background',
    'cite',
    'href',
    'itemtype',
    'longdesc',
    'poster',
    'src',
    'xlink:href'
  ]

  var ARIA_ATTRIBUTE_PATTERN = /^aria-[\w-]*$/i

  var DefaultWhitelist = {
    // Global attributes allowed on any supplied element below.
    '*': ['class', 'dir', 'id', 'lang', 'role', ARIA_ATTRIBUTE_PATTERN],
    a: ['target', 'href', 'title', 'rel'],
    area: [],
    b: [],
    br: [],
    col: [],
    code: [],
    div: [],
    em: [],
    hr: [],
    h1: [],
    h2: [],
    h3: [],
    h4: [],
    h5: [],
    h6: [],
    i: [],
    img: ['src', 'alt', 'title', 'width', 'height'],
    li: [],
    ol: [],
    p: [],
    pre: [],
    s: [],
    small: [],
    span: [],
    sub: [],
    sup: [],
    strong: [],
    u: [],
    ul: []
  }

  /**
   * A pattern that recognizes a commonly useful subset of URLs that are safe.
   *
   * Shoutout to Angular 7 https://github.com/angular/angular/blob/7.2.4/packages/core/src/sanitization/url_sanitizer.ts
   */
  var SAFE_URL_PATTERN = /^(?:(?:https?|mailto|ftp|tel|file):|[^&:/?#]*(?:[/?#]|$))/gi

  /**
   * A pattern that matches safe data URLs. Only matches image, video and audio types.
   *
   * Shoutout to Angular 7 https://github.com/angular/angular/blob/7.2.4/packages/core/src/sanitization/url_sanitizer.ts
   */
  var DATA_URL_PATTERN = /^data:(?:image\/(?:bmp|gif|jpeg|jpg|png|tiff|webp)|video\/(?:mpeg|mp4|ogg|webm)|audio\/(?:mp3|oga|ogg|opus));base64,[a-z0-9+/]+=*$/i

  function allowedAttribute(attr, allowedAttributeList) {
    var attrName = attr.nodeName.toLowerCase()

    if ($.inArray(attrName, allowedAttributeList) !== -1) {
      if ($.inArray(attrName, uriAttrs) !== -1) {
        return Boolean(attr.nodeValue.match(SAFE_URL_PATTERN) || attr.nodeValue.match(DATA_URL_PATTERN))
      }

      return true
    }

    var regExp = $(allowedAttributeList).filter(function (index, value) {
      return value instanceof RegExp
    })

    // Check if a regular expression validates the attribute.
    for (var i = 0, l = regExp.length; i < l; i++) {
      if (attrName.match(regExp[i])) {
        return true
      }
    }

    return false
  }

  function sanitizeHtml(unsafeHtml, whiteList, sanitizeFn) {
    if (unsafeHtml.length === 0) {
      return unsafeHtml
    }

    if (sanitizeFn && typeof sanitizeFn === 'function') {
      return sanitizeFn(unsafeHtml)
    }

    // IE 8 and below don't support createHTMLDocument
    if (!document.implementation || !document.implementation.createHTMLDocument) {
      return unsafeHtml
    }

    var createdDocument = document.implementation.createHTMLDocument('sanitization')
    createdDocument.body.innerHTML = unsafeHtml

    var whitelistKeys = $.map(whiteList, function (el, i) { return i })
    var elements = $(createdDocument.body).find('*')

    for (var i = 0, len = elements.length; i < len; i++) {
      var el = elements[i]
      var elName = el.nodeName.toLowerCase()

      if ($.inArray(elName, whitelistKeys) === -1) {
        el.parentNode.removeChild(el)

        continue
      }

      var attributeList = $.map(el.attributes, function (el) { return el })
      var whitelistedAttributes = [].concat(whiteList['*'] || [], whiteList[elName] || [])

      for (var j = 0, len2 = attributeList.length; j < len2; j++) {
        if (!allowedAttribute(attributeList[j], whitelistedAttributes)) {
          el.removeAttribute(attributeList[j].nodeName)
        }
      }
    }

    return createdDocument.body.innerHTML
  }

  // TOOLTIP PUBLIC CLASS DEFINITION
  // ===============================

  var Tooltip = function (element, options) {
    this.type       = null
    this.options    = null
    this.enabled    = null
    this.timeout    = null
    this.hoverState = null
    this.$element   = null
    this.inState    = null

    this.init('tooltip', element, options)
  }

  Tooltip.VERSION  = '3.4.1'

  Tooltip.TRANSITION_DURATION = 150

  Tooltip.DEFAULTS = {
    animation: true,
    placement: 'top',
    selector: false,
    template: '<div class="tooltip" role="tooltip"><div class="tooltip-arrow"></div><div class="tooltip-inner"></div></div>',
    trigger: 'hover focus',
    title: '',
    delay: 0,
    html: false,
    container: false,
    viewport: {
      selector: 'body',
      padding: 0
    },
    sanitize : true,
    sanitizeFn : null,
    whiteList : DefaultWhitelist
  }

  Tooltip.prototype.init = function (type, element, options) {
    this.enabled   = true
    this.type      = type
    this.$element  = $(element)
    this.options   = this.getOptions(options)
    this.$viewport = this.options.viewport && $(document).find($.isFunction(this.options.viewport) ? this.options.viewport.call(this, this.$element) : (this.options.viewport.selector || this.options.viewport))
    this.inState   = { click: false, hover: false, focus: false }

    if (this.$element[0] instanceof document.constructor && !this.options.selector) {
      throw new Error('`selector` option must be specified when initializing ' + this.type + ' on the window.document object!')
    }

    var triggers = this.options.trigger.split(' ')

    for (var i = triggers.length; i--;) {
      var trigger = triggers[i]

      if (trigger == 'click') {
        this.$element.on('click.' + this.type, this.options.selector, $.proxy(this.toggle, this))
      } else if (trigger != 'manual') {
        var eventIn  = trigger == 'hover' ? 'mouseenter' : 'focusin'
        var eventOut = trigger == 'hover' ? 'mouseleave' : 'focusout'

        this.$element.on(eventIn  + '.' + this.type, this.options.selector, $.proxy(this.enter, this))
        this.$element.on(eventOut + '.' + this.type, this.options.selector, $.proxy(this.leave, this))
      }
    }

    this.options.selector ?
      (this._options = $.extend({}, this.options, { trigger: 'manual', selector: '' })) :
      this.fixTitle()
  }

  Tooltip.prototype.getDefaults = function () {
    return Tooltip.DEFAULTS
  }

  Tooltip.prototype.getOptions = function (options) {
    var dataAttributes = this.$element.data()

    for (var dataAttr in dataAttributes) {
      if (dataAttributes.hasOwnProperty(dataAttr) && $.inArray(dataAttr, DISALLOWED_ATTRIBUTES) !== -1) {
        delete dataAttributes[dataAttr]
      }
    }

    options = $.extend({}, this.getDefaults(), dataAttributes, options)

    if (options.delay && typeof options.delay == 'number') {
      options.delay = {
        show: options.delay,
        hide: options.delay
      }
    }

    if (options.sanitize) {
      options.template = sanitizeHtml(options.template, options.whiteList, options.sanitizeFn)
    }

    return options
  }

  Tooltip.prototype.getDelegateOptions = function () {
    var options  = {}
    var defaults = this.getDefaults()

    this._options && $.each(this._options, function (key, value) {
      if (defaults[key] != value) options[key] = value
    })

    return options
  }

  Tooltip.prototype.enter = function (obj) {
    var self = obj instanceof this.constructor ?
      obj : $(obj.currentTarget).data('bs.' + this.type)

    if (!self) {
      self = new this.constructor(obj.currentTarget, this.getDelegateOptions())
      $(obj.currentTarget).data('bs.' + this.type, self)
    }

    if (obj instanceof $.Event) {
      self.inState[obj.type == 'focusin' ? 'focus' : 'hover'] = true
    }

    if (self.tip().hasClass('in') || self.hoverState == 'in') {
      self.hoverState = 'in'
      return
    }

    clearTimeout(self.timeout)

    self.hoverState = 'in'

    if (!self.options.delay || !self.options.delay.show) return self.show()

    self.timeout = setTimeout(function () {
      if (self.hoverState == 'in') self.show()
    }, self.options.delay.show)
  }

  Tooltip.prototype.isInStateTrue = function () {
    for (var key in this.inState) {
      if (this.inState[key]) return true
    }

    return false
  }

  Tooltip.prototype.leave = function (obj) {
    var self = obj instanceof this.constructor ?
      obj : $(obj.currentTarget).data('bs.' + this.type)

    if (!self) {
      self = new this.constructor(obj.currentTarget, this.getDelegateOptions())
      $(obj.currentTarget).data('bs.' + this.type, self)
    }

    if (obj instanceof $.Event) {
      self.inState[obj.type == 'focusout' ? 'focus' : 'hover'] = false
    }

    if (self.isInStateTrue()) return

    clearTimeout(self.timeout)

    self.hoverState = 'out'

    if (!self.options.delay || !self.options.delay.hide) return self.hide()

    self.timeout = setTimeout(function () {
      if (self.hoverState == 'out') self.hide()
    }, self.options.delay.hide)
  }

  Tooltip.prototype.show = function () {
    var e = $.Event('show.bs.' + this.type)

    if (this.hasContent() && this.enabled) {
      this.$element.trigger(e)

      var inDom = $.contains(this.$element[0].ownerDocument.documentElement, this.$element[0])
      if (e.isDefaultPrevented() || !inDom) return
      var that = this

      var $tip = this.tip()

      var tipId = this.getUID(this.type)

      this.setContent()
      $tip.attr('id', tipId)
      this.$element.attr('aria-describedby', tipId)

      if (this.options.animation) $tip.addClass('fade')

      var placement = typeof this.options.placement == 'function' ?
        this.options.placement.call(this, $tip[0], this.$element[0]) :
        this.options.placement

      var autoToken = /\s?auto?\s?/i
      var autoPlace = autoToken.test(placement)
      if (autoPlace) placement = placement.replace(autoToken, '') || 'top'

      $tip
        .detach()
        .css({ top: 0, left: 0, display: 'block' })
        .addClass(placement)
        .data('bs.' + this.type, this)

      this.options.container ? $tip.appendTo($(document).find(this.options.container)) : $tip.insertAfter(this.$element)
      this.$element.trigger('inserted.bs.' + this.type)

      var pos          = this.getPosition()
      var actualWidth  = $tip[0].offsetWidth
      var actualHeight = $tip[0].offsetHeight

      if (autoPlace) {
        var orgPlacement = placement
        var viewportDim = this.getPosition(this.$viewport)

        placement = placement == 'bottom' && pos.bottom + actualHeight > viewportDim.bottom ? 'top'    :
                    placement == 'top'    && pos.top    - actualHeight < viewportDim.top    ? 'bottom' :
                    placement == 'right'  && pos.right  + actualWidth  > viewportDim.width  ? 'left'   :
                    placement == 'left'   && pos.left   - actualWidth  < viewportDim.left   ? 'right'  :
                    placement

        $tip
          .removeClass(orgPlacement)
          .addClass(placement)
      }

      var calculatedOffset = this.getCalculatedOffset(placement, pos, actualWidth, actualHeight)

      this.applyPlacement(calculatedOffset, placement)

      var complete = function () {
        var prevHoverState = that.hoverState
        that.$element.trigger('shown.bs.' + that.type)
        that.hoverState = null

        if (prevHoverState == 'out') that.leave(that)
      }

      $.support.transition && this.$tip.hasClass('fade') ?
        $tip
          .one('bsTransitionEnd', complete)
          .emulateTransitionEnd(Tooltip.TRANSITION_DURATION) :
        complete()
    }
  }

  Tooltip.prototype.applyPlacement = function (offset, placement) {
    var $tip   = this.tip()
    var width  = $tip[0].offsetWidth
    var height = $tip[0].offsetHeight

    // manually read margins because getBoundingClientRect includes difference
    var marginTop = parseInt($tip.css('margin-top'), 10)
    var marginLeft = parseInt($tip.css('margin-left'), 10)

    // we must check for NaN for ie 8/9
    if (isNaN(marginTop))  marginTop  = 0
    if (isNaN(marginLeft)) marginLeft = 0

    offset.top  += marginTop
    offset.left += marginLeft

    // $.fn.offset doesn't round pixel values
    // so we use setOffset directly with our own function B-0
    $.offset.setOffset($tip[0], $.extend({
      using: function (props) {
        $tip.css({
          top: Math.round(props.top),
          left: Math.round(props.left)
        })
      }
    }, offset), 0)

    $tip.addClass('in')

    // check to see if placing tip in new offset caused the tip to resize itself
    var actualWidth  = $tip[0].offsetWidth
    var actualHeight = $tip[0].offsetHeight

    if (placement == 'top' && actualHeight != height) {
      offset.top = offset.top + height - actualHeight
    }

    var delta = this.getViewportAdjustedDelta(placement, offset, actualWidth, actualHeight)

    if (delta.left) offset.left += delta.left
    else offset.top += delta.top

    var isVertical          = /top|bottom/.test(placement)
    var arrowDelta          = isVertical ? delta.left * 2 - width + actualWidth : delta.top * 2 - height + actualHeight
    var arrowOffsetPosition = isVertical ? 'offsetWidth' : 'offsetHeight'

    $tip.offset(offset)
    this.replaceArrow(arrowDelta, $tip[0][arrowOffsetPosition], isVertical)
  }

  Tooltip.prototype.replaceArrow = function (delta, dimension, isVertical) {
    this.arrow()
      .css(isVertical ? 'left' : 'top', 50 * (1 - delta / dimension) + '%')
      .css(isVertical ? 'top' : 'left', '')
  }

  Tooltip.prototype.setContent = function () {
    var $tip  = this.tip()
    var title = this.getTitle()

    if (this.options.html) {
      if (this.options.sanitize) {
        title = sanitizeHtml(title, this.options.whiteList, this.options.sanitizeFn)
      }

      $tip.find('.tooltip-inner').html(title)
    } else {
      $tip.find('.tooltip-inner').text(title)
    }

    $tip.removeClass('fade in top bottom left right')
  }

  Tooltip.prototype.hide = function (callback) {
    var that = this
    var $tip = $(this.$tip)
    var e    = $.Event('hide.bs.' + this.type)

    function complete() {
      if (that.hoverState != 'in') $tip.detach()
      if (that.$element) { // TODO: Check whether guarding this code with this `if` is really necessary.
        that.$element
          .removeAttr('aria-describedby')
          .trigger('hidden.bs.' + that.type)
      }
      callback && callback()
    }

    this.$element.trigger(e)

    if (e.isDefaultPrevented()) return

    $tip.removeClass('in')

    $.support.transition && $tip.hasClass('fade') ?
      $tip
        .one('bsTransitionEnd', complete)
        .emulateTransitionEnd(Tooltip.TRANSITION_DURATION) :
      complete()

    this.hoverState = null

    return this
  }

  Tooltip.prototype.fixTitle = function () {
    var $e = this.$element
    if ($e.attr('title') || typeof $e.attr('data-original-title') != 'string') {
      $e.attr('data-original-title', $e.attr('title') || '').attr('title', '')
    }
  }

  Tooltip.prototype.hasContent = function () {
    return this.getTitle()
  }

  Tooltip.prototype.getPosition = function ($element) {
    $element   = $element || this.$element

    var el     = $element[0]
    var isBody = el.tagName == 'BODY'

    var elRect    = el.getBoundingClientRect()
    if (elRect.width == null) {
      // width and height are missing in IE8, so compute them manually; see https://github.com/twbs/bootstrap/issues/14093
      elRect = $.extend({}, elRect, { width: elRect.right - elRect.left, height: elRect.bottom - elRect.top })
    }
    var isSvg = window.SVGElement && el instanceof window.SVGElement
    // Avoid using $.offset() on SVGs since it gives incorrect results in jQuery 3.
    // See https://github.com/twbs/bootstrap/issues/20280
    var elOffset  = isBody ? { top: 0, left: 0 } : (isSvg ? null : $element.offset())
    var scroll    = { scroll: isBody ? document.documentElement.scrollTop || document.body.scrollTop : $element.scrollTop() }
    var outerDims = isBody ? { width: $(window).width(), height: $(window).height() } : null

    return $.extend({}, elRect, scroll, outerDims, elOffset)
  }

  Tooltip.prototype.getCalculatedOffset = function (placement, pos, actualWidth, actualHeight) {
    return placement == 'bottom' ? { top: pos.top + pos.height,   left: pos.left + pos.width / 2 - actualWidth / 2 } :
           placement == 'top'    ? { top: pos.top - actualHeight, left: pos.left + pos.width / 2 - actualWidth / 2 } :
           placement == 'left'   ? { top: pos.top + pos.height / 2 - actualHeight / 2, left: pos.left - actualWidth } :
        /* placement == 'right' */ { top: pos.top + pos.height / 2 - actualHeight / 2, left: pos.left + pos.width }

  }

  Tooltip.prototype.getViewportAdjustedDelta = function (placement, pos, actualWidth, actualHeight) {
    var delta = { top: 0, left: 0 }
    if (!this.$viewport) return delta

    var viewportPadding = this.options.viewport && this.options.viewport.padding || 0
    var viewportDimensions = this.getPosition(this.$viewport)

    if (/right|left/.test(placement)) {
      var topEdgeOffset    = pos.top - viewportPadding - viewportDimensions.scroll
      var bottomEdgeOffset = pos.top + viewportPadding - viewportDimensions.scroll + actualHeight
      if (topEdgeOffset < viewportDimensions.top) { // top overflow
        delta.top = viewportDimensions.top - topEdgeOffset
      } else if (bottomEdgeOffset > viewportDimensions.top + viewportDimensions.height) { // bottom overflow
        delta.top = viewportDimensions.top + viewportDimensions.height - bottomEdgeOffset
      }
    } else {
      var leftEdgeOffset  = pos.left - viewportPadding
      var rightEdgeOffset = pos.left + viewportPadding + actualWidth
      if (leftEdgeOffset < viewportDimensions.left) { // left overflow
        delta.left = viewportDimensions.left - leftEdgeOffset
      } else if (rightEdgeOffset > viewportDimensions.right) { // right overflow
        delta.left = viewportDimensions.left + viewportDimensions.width - rightEdgeOffset
      }
    }

    return delta
  }

  Tooltip.prototype.getTitle = function () {
    var title
    var $e = this.$element
    var o  = this.options

    title = $e.attr('data-original-title')
      || (typeof o.title == 'function' ? o.title.call($e[0]) :  o.title)

    return title
  }

  Tooltip.prototype.getUID = function (prefix) {
    do prefix += ~~(Math.random() * 1000000)
    while (document.getElementById(prefix))
    return prefix
  }

  Tooltip.prototype.tip = function () {
    if (!this.$tip) {
      this.$tip = $(this.options.template)
      if (this.$tip.length != 1) {
        throw new Error(this.type + ' `template` option must consist of exactly 1 top-level element!')
      }
    }
    return this.$tip
  }

  Tooltip.prototype.arrow = function () {
    return (this.$arrow = this.$arrow || this.tip().find('.tooltip-arrow'))
  }

  Tooltip.prototype.enable = function () {
    this.enabled = true
  }

  Tooltip.prototype.disable = function () {
    this.enabled = false
  }

  Tooltip.prototype.toggleEnabled = function () {
    this.enabled = !this.enabled
  }

  Tooltip.prototype.toggle = function (e) {
    var self = this
    if (e) {
      self = $(e.currentTarget).data('bs.' + this.type)
      if (!self) {
        self = new this.constructor(e.currentTarget, this.getDelegateOptions())
        $(e.currentTarget).data('bs.' + this.type, self)
      }
    }

    if (e) {
      self.inState.click = !self.inState.click
      if (self.isInStateTrue()) self.enter(self)
      else self.leave(self)
    } else {
      self.tip().hasClass('in') ? self.leave(self) : self.enter(self)
    }
  }

  Tooltip.prototype.destroy = function () {
    var that = this
    clearTimeout(this.timeout)
    this.hide(function () {
      that.$element.off('.' + that.type).removeData('bs.' + that.type)
      if (that.$tip) {
        that.$tip.detach()
      }
      that.$tip = null
      that.$arrow = null
      that.$viewport = null
      that.$element = null
    })
  }

  Tooltip.prototype.sanitizeHtml = function (unsafeHtml) {
    return sanitizeHtml(unsafeHtml, this.options.whiteList, this.options.sanitizeFn)
  }

  // TOOLTIP PLUGIN DEFINITION
  // =========================

  function Plugin(option) {
    return this.each(function () {
      var $this   = $(this)
      var data    = $this.data('bs.tooltip')
      var options = typeof option == 'object' && option

      if (!data && /destroy|hide/.test(option)) return
      if (!data) $this.data('bs.tooltip', (data = new Tooltip(this, options)))
      if (typeof option == 'string') data[option]()
    })
  }

  var old = $.fn.tooltip

  $.fn.tooltip             = Plugin
  $.fn.tooltip.Constructor = Tooltip


  // TOOLTIP NO CONFLICT
  // ===================

  $.fn.tooltip.noConflict = function () {
    $.fn.tooltip = old
    return this
  }

}(jQuery);
/* ========================================================================
 * Bootstrap: popover.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#popovers
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // POPOVER PUBLIC CLASS DEFINITION
  // ===============================

  var Popover = function (element, options) {
    this.init('popover', element, options)
  }

  if (!$.fn.tooltip) throw new Error('Popover requires tooltip.js')

  Popover.VERSION  = '3.4.1'

  Popover.DEFAULTS = $.extend({}, $.fn.tooltip.Constructor.DEFAULTS, {
    placement: 'right',
    trigger: 'click',
    content: '',
    template: '<div class="popover" role="tooltip"><div class="arrow"></div><h3 class="popover-title"></h3><div class="popover-content"></div></div>'
  })


  // NOTE: POPOVER EXTENDS tooltip.js
  // ================================

  Popover.prototype = $.extend({}, $.fn.tooltip.Constructor.prototype)

  Popover.prototype.constructor = Popover

  Popover.prototype.getDefaults = function () {
    return Popover.DEFAULTS
  }

  Popover.prototype.setContent = function () {
    var $tip    = this.tip()
    var title   = this.getTitle()
    var content = this.getContent()

    if (this.options.html) {
      var typeContent = typeof content

      if (this.options.sanitize) {
        title = this.sanitizeHtml(title)

        if (typeContent === 'string') {
          content = this.sanitizeHtml(content)
        }
      }

      $tip.find('.popover-title').html(title)
      $tip.find('.popover-content').children().detach().end()[
        typeContent === 'string' ? 'html' : 'append'
      ](content)
    } else {
      $tip.find('.popover-title').text(title)
      $tip.find('.popover-content').children().detach().end().text(content)
    }

    $tip.removeClass('fade top bottom left right in')

    // IE8 doesn't accept hiding via the `:empty` pseudo selector, we have to do
    // this manually by checking the contents.
    if (!$tip.find('.popover-title').html()) $tip.find('.popover-title').hide()
  }

  Popover.prototype.hasContent = function () {
    return this.getTitle() || this.getContent()
  }

  Popover.prototype.getContent = function () {
    var $e = this.$element
    var o  = this.options

    return $e.attr('data-content')
      || (typeof o.content == 'function' ?
        o.content.call($e[0]) :
        o.content)
  }

  Popover.prototype.arrow = function () {
    return (this.$arrow = this.$arrow || this.tip().find('.arrow'))
  }


  // POPOVER PLUGIN DEFINITION
  // =========================

  function Plugin(option) {
    return this.each(function () {
      var $this   = $(this)
      var data    = $this.data('bs.popover')
      var options = typeof option == 'object' && option

      if (!data && /destroy|hide/.test(option)) return
      if (!data) $this.data('bs.popover', (data = new Popover(this, options)))
      if (typeof option == 'string') data[option]()
    })
  }

  var old = $.fn.popover

  $.fn.popover             = Plugin
  $.fn.popover.Constructor = Popover


  // POPOVER NO CONFLICT
  // ===================

  $.fn.popover.noConflict = function () {
    $.fn.popover = old
    return this
  }

}(jQuery);
















// Google Analytics tracking

class Tracker {
  constructor(){
    this.playlistItem = null;    // the jwplayer playlist item object being played
    this.started = 0;            // timestamp of the last play event
    this.startPosition = 0;      // keeps track of the currently watched segments start position
    this.lastPosition = 0;       // the last position that was recorded (used to calculate a watched segment)
    this.totalTimePrimary = 0;   // keeps total of time spend watching (most accurate)
    this.totalTimeSecondary = 0; // a different way to track total time spent watching (works for live streams)
    this.watchedSegments = [];   // a collection of the watched segments of the video, used for % watched
    this.duration = -1;          // total length of the video
    this.paused = false;         // indicates whether the player is currently paused
    this.playSent = false;       // indicates if we already sent the play event for this video
    this.doneSent = false;       // indicates if we already send the stop or complete event for this video
  }
}

var ActivityTracker = {
  playerAccessKey: null,
  playerG4TrackingCode: null,
  globalPlayerTrackingCode: null,
  tracker: null,
  chapters: {},
  organizationUuid: null,
  anonymizeIp: null,
  mobileAppType: null,
  collectionName: null,

  initializeAnalyticsLibrary: function() {
    // Make the GA cookie name distinct for each player. This is important
    // because all of our player will share the same cookie domain, so we want
    // a different GA cookie for each player that a given user may view.
    // Without this, each player a viewer visits will share a session, which
    // is not desirable.
    let trackerOptions = {
      'cookieName': 'telvue-' + ActivityTracker.playerAccessKey,
      'anonymize_ip': ActivityTracker.anonymizeIp
    };
    if (window.location.hostname == 'localhost') {
      trackerOptions['cookieDomain'] = 'none';
    }

    // Connect uses a single Global Tracking account to capture all traffic across all orgs and apps
    // then later in reporting, filters by org uuid or player access key
    // initialize Global Tracking

    gtag('config', ActivityTracker.globalPlayerTrackingCode, { 
      'anonymize_ip': ActivityTracker.anonymizeIp
    });
    
    gtag('set', 'user_properties', { 
      organization_uuid: ActivityTracker.organizationUuid,
      app_type: appType(),
      app_uuid: ActivityTracker.playerAccessKey,
    });

    if (ActivityTracker.playerHasG4TrackingCode()) {
      // register tracking with player specific g4 tracking code if it's set
      // no need to conditionally load gtag.js library code, it is already loaded by default
      //    for player global code
      gtag('config', ActivityTracker.playerG4TrackingCode, trackerOptions);
    }


    function appType() {
      if (ActivityTracker.mobileAppType.length > 0) {
        return ActivityTracker.mobileAppType
      } else {
        return 'web'
      }
    }
  },

  // Reset the tracker object every time we are on
  // a new playlist item.
  onPlaylistItem: function() {
    ActivityTracker.tracker = new Tracker();
    ActivityTracker.tracker.playlistItem = jwplayer('jw_player_instance').getPlaylistItem();
  },

  onPlay: function() {
    // Set focus for keyboard shortcuts after play is clicked, 
    // proved to be required for Chrome 
    jwplayer('jw_player_instance').getContainer().focus();

    let videoStartParams = {
      organization_uuid: ActivityTracker.organizationUuid,
      video_id: PathHelpers.videoIdFromUrl(),
      video_type: PathHelpers.videoTypeFromUrl(),
      video_title: ActivityTracker.tracker.playlistItem.title,
      video_collection_id: PathHelpers.collectionIdFromUrl(),
      video_collection_type: PathHelpers.collectionTypeFromUrl(),
      video_collection_name: ActivityTracker.collectionName,
      video_provider: 'TelVue CloudCast',
      send_to: ActivityTracker.globalPlayerTrackingCode
    }

    if (ActivityTracker.tracker.paused === false && ActivityTracker.tracker.playSent === false) {
      // global
      gtag('event', 'video_start', videoStartParams);

      // individual tracker
      if (ActivityTracker.playerHasG4TrackingCode()) {
        videoStartParams.send_to = ActivityTracker.playerG4TrackingCode;
        gtag('event', 'video_start', videoStartParams);
      }
      
      ActivityTracker.tracker.playSent = true;
      ActivityTracker.tracker.doneSent = false;
    } else if (ActivityTracker.tracker.paused) {
      ActivityTracker.tracker.paused = false;
      ActivityTracker.handleVideoEvent('video_resume', false);
    }

    // Record the timestamp when this happened for our secondary time tracking
    ActivityTracker.tracker.started = (new Date()).getTime();
  },

  // Increment our secondary timer as the user is no longer playing video
  onPause: function(event) {
    // Only register a pause if the video is viewable. Auto pause from
    // a user changing tabs when the video is muted is not supported
    // as there is no way to distinguish that from a pause triggered when
    // leaving the page, tab, or browser. Seems better to skip sending pause/resume
    // pair from a tab switch that a user did not actually intentially click on the player 
    // than having extraneous pause events right before a stop from leaving the page.
    if (event.viewable === 1) {
      ActivityTracker.tracker.paused = true;
      ActivityTracker.handleVideoEvent('video_pause', false);
    }
  },

  // Increment our secondary timer as the user is no longer playing video
  onBuffer: function() {
    ActivityTracker.recordTimeWatched();
  },

  // A good indicator that the user finished watching the video or went to play another
  // We need to make our last recordings of the watched segments and time watched before
  // sending events off to google
  onIdle: function() {
    let vidDuration = jwplayer('jw_player_instance').getDuration();
    let vidPosition = jwplayer('jw_player_instance').getPosition();
    // if a video has actually reached the very end, let the onComplete trigger handle
    if (vidPosition != vidDuration) {
      ActivityTracker.handleVideoEvent('video_stop', true);
    }
  },

  onError: function(event) {
    gtag('event', 'video_error', { 
      send_to: ActivityTracker.globalPlayerTrackingCode,
      error_code: event.code,
      error_type: event.sourceError.type,
      video_title: ActivityTracker.tracker.playlistItem.title,
      organization_uuid: ActivityTracker.organizationUuid
    });
  },

  onComplete: function() {
    ActivityTracker.handleVideoEvent('video_complete', true);
  },

  onTime: function(event) {
    if (ActivityTracker.chapters.length > 0) ActivityTracker.emitChapterEvents(event);

    // We get an accurate duration of the video here
    if (event.duration > 0) {
      ActivityTracker.tracker.duration = event.duration;
    }

    let currentPosition = event.position;
    let timediff = currentPosition - ActivityTracker.tracker.lastPosition;

    // If the time difference is less than a second, that indicates a normal playback
    // without a seek. Just add to total time.
    if (Math.abs(timediff) < 1) {
      ActivityTracker.tracker.totalTimePrimary = ActivityTracker.tracker.totalTimePrimary + (currentPosition - ActivityTracker.tracker.lastPosition);
    // Otherwise, the user probably seeked and we want to record the segment of time
    // they watched.
    } else {
      ActivityTracker.recordWatchedSegment();

      // Reset start position to where we are now, so a new segment can start
      ActivityTracker.tracker.startPosition = currentPosition;
    }

    ActivityTracker.tracker.lastPosition = currentPosition;
  },

  onSeek: function(event) {
    gtag('event', 'video_seek', {
      send_to: ActivityTracker.globalPlayerTrackingCode,
      video_title: ActivityTracker.tracker.playlistItem.title,
      video_id: PathHelpers.videoIdFromUrl(),
      video_type: PathHelpers.videoTypeFromUrl(),
      seek_from: event.position,
      seek_to: event.offset
    });
  },

  emitChapterEvents: function(event){
    ActivityTracker.chapters.map((chapter) => {
      if (Math.floor(event.position) == chapter.start_time) {
        const chapterStart = new CustomEvent('chapterStarted', {
          detail: { 
            chapterId: chapter.id
          }
        });
        window.dispatchEvent(chapterStart);

      } else if (Math.floor(event.position) == chapter.end_time) {
        const chapterEnd = new CustomEvent('chapterEnded', {
          detail: { 
            chapterId: chapter.id
          }
        });
        window.dispatchEvent(chapterEnd);
      }
    });
  },


  // Called when the video has entered a state that should send an anlytics event.
  // Specifically for pause/resume, stop, complete, including when a user
  // finished or left page / loaded new video / etc.
  // Here we send the % watched and seconds played beacons to GA
  handleVideoEvent: function(event_name, done) {
    if (ActivityTracker.tracker) {
      // Since this is called when the video has reached it's end, we need to add the final
      // time and percentage watched segments up
      ActivityTracker.recordWatchedSegment();
      ActivityTracker.recordTimeWatched();

      const pct = ActivityTracker.calculatePercentageWatched();
      let time;
      if (ActivityTracker.tracker.totalTimePrimary > 0) {
        time = ActivityTracker.tracker.totalTimePrimary;
      } else {
        time = ActivityTracker.tracker.totalTimePrimary / 1000;
      }

      let videoEventParams = { 
        send_to: ActivityTracker.globalPlayerTrackingCode,
        video_title: ActivityTracker.tracker.playlistItem.title,
        organization_uuid: ActivityTracker.organizationUuid,
        video_id: PathHelpers.videoIdFromUrl(),
        video_type: PathHelpers.videoTypeFromUrl(),
        video_collection_id: PathHelpers.collectionIdFromUrl(),
        video_collection_type: PathHelpers.collectionTypeFromUrl(),
        video_collection_name: ActivityTracker.collectionName,
        video_provider: 'TelVue CloudCast'
      };
    
      if (pct > -1) {
        videoEventParams.video_percent = pct;
      }

      // Ensure null is never sent for seconds played
      let secondsPlayed = 0;
      if (parseInt(time) >= 0) { 
        secondsPlayed = parseInt(time);
      }
      videoEventParams.video_seconds_played = secondsPlayed;

      let sendEvent = true;
      // Don't send additional events if the video_start was never sent,
      // or video_stop or video_complete was already sent. Also guards against
      // an extra pause being sent before a stop when leaving the page during play.
      if ((ActivityTracker.tracker.playSent === false) || (ActivityTracker.tracker.doneSent === true)) {
        sendEvent = false; 
      }

      if (sendEvent) {
        gtag('event', event_name, videoEventParams);

        if (ActivityTracker.playerHasG4TrackingCode()) {
          videoEventParams.send_to = ActivityTracker.playerG4TrackingCode;
          gtag('event', event_name, videoEventParams);
        }

        if (done) {
          ActivityTracker.tracker.doneSent = true;
        }
      }

      if (done) {
        // Use the primary time tracker if it's available. For live streams it won't be
        // and we'll use the fallback, which is slightly less accurate.

        ActivityTracker.tracker = new Tracker();
        ActivityTracker.tracker.playlistItem = jwplayer('jw_player_instance').getPlaylistItem();
      }
    }
  },

  // push the watched segment information to our collection. This is used later on
  // to determine percentage of video watched
  recordWatchedSegment: function() {
    let start = {
      time: ActivityTracker.tracker.startPosition,
      type: 's'
    }
    let end = {
      time: ActivityTracker.tracker.lastPosition,
      type: 'e'
    }
    ActivityTracker.tracker.watchedSegments.push(start);
    ActivityTracker.tracker.watchedSegments.push(end);
  },

  // Will add to our secondary time counter by taking the difference of
  // the current time and the last recorded play time
  recordTimeWatched: function() {
    if (ActivityTracker.tracker.started > 0) {
      ActivityTracker.tracker.totalTimeSecondary += (new Date()).getTime() - ActivityTracker.tracker.started;
      ActivityTracker.tracker.started = 0;
    }
  },


  // Gather the percentage watched of the video. We do this by "squashing" down all of
  // the recorded time segments the user watched, and then adding the time of the segments
  // together and comparing to the duration. See the following SO post for the algorithim:
  // http://stackoverflow.com/questions/7468948/problem-calculating-overlapping-date-ranges
  calculatePercentageWatched: function() {
    // If we don't have a duration for the current item, probably means it's a live stream
    // and we can't figure out percentage watched
    if (ActivityTracker.tracker.duration === -1) {
      return -1;
    }

    // Sort numerically
    let segs = ActivityTracker.tracker.watchedSegments.sort( (a,b) => {
      return a.time - b.time;
    });

    let counter = 0;       // goes up or down based on if we process a start or end time
    let newCount = 0;     // holds what the next counter value is
    let currentStart = 0; // keeps track of the current "squashed" segment start
    let timeWatched = 0;  // a running total of the amount of time actually played back

    while (segs.length > 0) {
      let currentSegment = segs.shift();

      newCount = counter + 1;

      // counter will go up if we hit another start time,
      // or down if we hit an end time
      if (currentSegment.type == 's') {
        newCount = counter + 1;
      } else {
        newCount = counter - 1;
      }

      // If the counter goes from 0-1 or 1-0 then we've hit the beginning or end
      // of a squashed segment, respectively.
      if (counter == 0 && newCount == 1) {
        currentStart = currentSegment.time;
      } else if (counter == 1 && newCount == 0) {
        // End of this squashed segment, just add the time of the segment to
        // our total counter.
        timeWatched += (currentSegment.time - currentStart);
      }

      counter = newCount;
    }

    // If this worked right, the counter should have ended back at 0. If it didn't, something
    // clearly went wrong and we should throw out any calculations we've done.
    let percentageWatched;
    if (counter == 0) {
      percentageWatched = (timeWatched / ActivityTracker.tracker.duration) * 100;
    } else {
      percentageWatched = -1;
    }

    return percentageWatched;
  },

  playerHasG4TrackingCode: function() {
    return (ActivityTracker.playerG4TrackingCode != null && ActivityTracker.playerG4TrackingCode.length > 0);
  }
};
var BannerAds = {
  allAds: function() {
    return document.querySelectorAll('.banner-ad-container');
  },

  setInitialState: function() {
    let footer = document.querySelector('#ad_footer');
    // when the dismiss "X" control is clicked we store off the timestamp at the click
    // event plus 24 hours, we now compare that timestamp if it exists with current timestamp
    // when page is being built, if it is still not past cancel + 24 hours, we don't show these banners
    if (Date.now() < parseInt(localStorage['player.cancelAdsTimeStamp'])) {
      footer.style.display = 'none';
    }
  },

  addClickListenerToBannerAdDismissX: function() {
    let bannerAdDismissControls = document.querySelectorAll('#ad_footer i');
    let footer = document.querySelector('#ad_footer');
    let now = new Date();

    bannerAdDismissControls.forEach(ba => {
      ba.addEventListener("click", function(){
        // cancel display of banner ads for 24 hours
        localStorage['player.cancelAdsTimeStamp'] = now.setDate(now.getDate() + 1);
        footer.style.display = 'none';
      });
    });
  },

  rotateBanner: function(currentIndex) {
    let nextIndex = (currentIndex == BannerAds.maxIndex) ? 0 : currentIndex + 1;

    BannerAds.allAds()[currentIndex].style.display = 'none';
    BannerAds.allAds()[nextIndex].style.display = 'inline-block';

    BannerAds.setupTimeout(nextIndex);
  },

  setupTimeout: function(currentIndex) {
    if (BannerAds.allAds().length == 0) { return };

    let duration = BannerAds.allAds()[currentIndex].dataset.displayduration * 1000;
    setTimeout(()=>{
      BannerAds.rotateBanner(currentIndex);
    }, duration);
  }
};


document.addEventListener("DOMContentLoaded", function(){
  BannerAds.maxIndex = BannerAds.allAds().length - 1;
  BannerAds.setInitialState();
  BannerAds.addClickListenerToBannerAdDismissX();
  BannerAds.setupTimeout(0);
});

var Captions = {
  lastTrackedTimeInSecs: 0,

  addEventListenerToSearchButton: function() {
    let searchSubmitButton = document.querySelector('div.sync-video-checkbox-container button');

    searchSubmitButton.addEventListener('click', function(){
      let searchPhrase = document.querySelector('input.caption-search-term').value;
      let url = searchSubmitButton.dataset.url;
      let container = document.querySelector('div.caption-text-container');
      let searchResultsMetadataContainer = document.querySelector('div.caption-search-results-metadata');
      
      fetch(url + '&search_phrase=' + searchPhrase).then(response => response.text())
        .then(html => container.innerHTML = html)
        .then(function(){
          if (searchPhrase === '') {
            // search will return all captions if empty string is searched
            searchResultsMetadataContainer.innerHTML = null;
          } else {
            // search returned results
            let searchResultsCount = document.querySelectorAll('ol.closed-captions-def-list-container li').length;
            searchResultsMetadataContainer.innerHTML = '<p role="status">Displaying ' + searchResultsCount 
              + ' results for search phrase: "' + searchPhrase + '" <button class="' + 'video-search-clear-btn' + '" aria-label="clear search"><icon class="fas fa-times-circle"></icon></span></p>';
            // uncheck the "Synchronize Video and Captions checkbox", don't try to sync search results
            document.querySelector('input#synch_video_and_captions').checked = false;

            // TODO: Notify Google Analytics of search being performed
            // if google analytics enhanced tracking doesn't see this search because
            // it is done via ajax and not a traditional form submission, manually send info to Google

          }
        });
    });
  },

  addJwPlayerScrubListener: function() {
    jwplayer('jw_player_instance').on('seek', Captions.jwPlayerScrubHandler);
    jwplayer('jw_player_instance').on('time', Captions.jwPlayerContinuousPlayHandler);
  },

  jwPlayerScrubHandler: function(event) {
    if (Captions.searchPerformed()) return;

    let captionArea = document.querySelector('div.caption-text-container');
    // scroll caption area to whereever we've seeked to
    let currentTimeSecs = event.offset;
    let targetTimestamp = null;
    const timeStamps = document.querySelectorAll('li.caption-timestamp');

    for (let ct of timeStamps) {
      if (parseInt(ct.dataset.startTime) >= parseInt(currentTimeSecs)) {
        targetTimestamp = ct;
        break;
      }
    }

    // scrollIntoView not working
    //targetTimestamp.scrollIntoView({ behavior: 'smooth', block: 'start'});
    captionArea.scrollTop = targetTimestamp.offsetTop - captionArea.offsetTop - 75;
  },

  jwPlayerContinuousPlayHandler: function(event){
    if (Captions.searchPerformed()) return;
    // while the video is playing, make sure captions scroll to keep up
    let currentTimeSecs = parseInt(event.position);

    if (currentTimeSecs > Captions.lastTrackedTimeInSecs) {
      
      // a second has elapsed, check if we need to scroll the captions
      let captionArea = document.querySelector('div.caption-text-container');

      let targetTimestamp = null;
      const timeStamps = document.querySelectorAll('li.caption-timestamp');

      for (let ct of timeStamps) {
        if (parseInt(ct.dataset.startTime) >= parseInt(currentTimeSecs)) {
          targetTimestamp = ct;
          break;
        }
      }

      captionArea.scrollTop = targetTimestamp.offsetTop - captionArea.offsetTop - 75;
    }

    Captions.lastTrackedTimeInSecs = currentTimeSecs;
  },



  addCaptionAreaListeners: function() {
    let captionArea = document.querySelector('div.caption-text-container');
    
    captionArea.addEventListener('scroll', Captions.captionAreaScrollHandler);
    jwplayer('jw_player_instance').off('time'); // remove this otherwise caption scroll will break sync
  },

  captionTimestampClickHandler: function(event) {
    if (event.target.nodeName === 'BUTTON') {
      jwplayer('jw_player_instance').seek(event.target.dataset.startTime);
    }
  },

  captionAreaScrollHandler: function(event) {
    if (Captions.searchPerformed()) return;

    let captionArea = document.querySelector('div.caption-text-container');
    let topCaptionDt = null;
    document.querySelectorAll('li.caption-timestamp').forEach(ct => {
      if ((ct.offsetTop - 300 - captionArea.scrollTop) < 0) {
        topCaptionDt = ct;
        return;
      }
    });

    jwplayer('jw_player_instance').seek(topCaptionDt.dataset.startTime);
  },

  addEventListenerToSyncVideoAndCaptionsCheckbox: function() {
    let checkbox = document.querySelector('input#synch_video_and_captions');
    let jwPlayerArea = document.querySelector('div#player-container');
    let captionArea = document.querySelector('div.caption-text-container');

    checkbox.addEventListener('click', function(){
      if (this.checked) {
        jwPlayerArea.addEventListener('mouseenter', Captions.addJwPlayerScrubListener);
        captionArea.addEventListener('mouseenter', Captions.addCaptionAreaListeners);


        jwPlayerArea.addEventListener('mouseleave', function(){
          jwplayer('jw_player_instance').off('seek');
        });

        captionArea.addEventListener('mouseleave', function(){
          captionArea.removeEventListener('scroll', Captions.captionAreaScrollHandler);
        });


      } else {
        // remove all related event listeners
        Captions.removeAllCaptionSyncListeners();
      }
    });

  },

  removeAllCaptionSyncListeners: function() {
    let jwPlayerArea = document.querySelector('div#player-container');
    let captionArea = document.querySelector('div.caption-text-container');

    jwPlayerArea.removeEventListener('mouseenter', Captions.addJwPlayerScrubListener);
    captionArea.removeEventListener('mouseenter', Captions.addCaptionAreaListeners);
    jwplayer('jw_player_instance').off('seek');
    jwplayer('jw_player_instance').off('time');
  },


  addEventListenerToCaptionSearchClearControl: function(){
    // this listener is on parent since child doesn't always exist
    let clearControlParent = document.querySelector('div.caption-search-results-metadata');
    clearControlParent.addEventListener('click', function(e){
      if (e.target.nodeName === 'ICON') {
        let searchSubmitButton = document.querySelector('div.sync-video-checkbox-container button');
        let url = searchSubmitButton.dataset.url;
        let container = document.querySelector('div.caption-text-container');
        let searchResultsMetadataContainer = document.querySelector('div.caption-search-results-metadata');
        fetch(url + '&search_phrase=').then(response => response.text())
          .then(html => container.innerHTML = html)
          .then(function(){
            searchResultsMetadataContainer.innerHTML = null;
            document.querySelector('input.caption-search-term').value = null;
          });
      }
    });
  },

  addEventListenerToCaptionSearchTextInputField: function() {
    let searchSubmitButton = document.querySelector('div.sync-video-checkbox-container button');
    // this is to trap carriage return key presses
    let searchTextInputField = document.querySelector('input.caption-search-term');
    searchTextInputField.addEventListener('keydown', function(e){
      if (e.key === 'Enter') {

        searchSubmitButton.click();
      }
    });
  },

  searchPerformed: function() {
    // whether there is content or not in this DOM object is a proxy for whether a search was performed or not
    return document.querySelector('div.caption-search-results-metadata').innerHTML.length !== 0;
  },

  addEventListenerToCaptionTimestamps: function() {
    let captionArea = document.querySelector('div.caption-text-container');
    captionArea.addEventListener('click', Captions.captionTimestampClickHandler);
  }
};

document.addEventListener("DOMContentLoaded", function(){
  let captionSidebar = document.querySelector('div#captions-text-container');

  if (captionSidebar != null) {
    Captions.addEventListenerToSearchButton();
    Captions.addEventListenerToCaptionSearchClearControl();
    Captions.addEventListenerToCaptionSearchTextInputField();
    Captions.addEventListenerToSyncVideoAndCaptionsCheckbox();
    Captions.addEventListenerToCaptionTimestamps();
  }
});
var Categories = {

};

document.addEventListener("DOMContentLoaded", function(){
  let cssClasses = document.querySelector('div#main').classList;
  if (cssClasses.contains('category')) {
    Videos.addClickHandlerToShowOrHideMoreControls();
  }
  
});
var Chapters = {
  addEventListenerForChapterStart: function() {
    window.addEventListener('chapterStarted', (event) => {
      Chapters.updateChapterHighlighting(event.detail.chapterId);
    });
  },

  addEventListenerForChapterEnd: function() {
    window.addEventListener('chapterEnded', (event) => {
      Chapters.removeChapterHighlightFor(event.detail.chapterId);
    });
  },


  updateChapterHighlighting: function(chapterId) {
    Chapters.removeAllChapterHighlights();
    Chapters.addChapterHighlight(chapterId);
    //Chapters.scrollToChapter(chapterId);
  },

  removeAllChapterHighlights: function() {
    let chapterRows = document.querySelectorAll('li.chapter');
    chapterRows.forEach(row => {
      // not chapters that have end time defined, those are individually dimmed
      // when the chapter end time is hit
      //if (row.dataset.endTime == undefined) {
        row.classList.remove('active');
      //}
    });
  },

  removeChapterHighlightFor: function(chapterId) {
    let chapterRow = document.querySelector(`li.chapter[data-id="${chapterId}"]`);
    chapterRow.classList.remove('active');
  },

  addChapterHighlight: function(chapterId) {
    let chapterRow = document.querySelector(`li.chapter[data-id="${chapterId}"]`);
    chapterRow.classList.add('active');
  },

  // won't need this if we remove double scrolling within chapter container div
  scrollToChapter: function(chapterId) {
    let chapterRow = document.querySelector(`li.chapter[data-id="${chapterId}"]`);
    let chapterContainer = document.querySelector('div#chapters');
    //chapters.scrollTop(chapterContainer.scrollTop() - chapterContainer.offset().top + chapterRow.offset().top);
  },

  addDescriptionTextToggle: function() {
    let descriptionToggleLinks = document.querySelectorAll('button.chapter-description-toggle');
    descriptionToggleLinks.forEach(link => {
      link.addEventListener('click', function(e){
        e.preventDefault();
        
        let chapterId = link.dataset.chapterId;
        let chapterDescription = document.querySelector(`p.description[data-chapter-id="${chapterId}"]`);

        if (chapterDescription.style.display == '' || chapterDescription.style.display == 'none') {
          $(chapterDescription).slideDown();
          link.innerHTML = 'Hide Description';
        } else {
          $(chapterDescription).slideUp();
          link.innerHTML = 'Show Description';
        }
      });
    });
  }
};

document.addEventListener("DOMContentLoaded", function(){
  if (document.querySelector('nav#chapters-container') != null) {
    Chapters.addEventListenerForChapterStart();
    Chapters.addEventListenerForChapterEnd();
    Chapters.addDescriptionTextToggle();
  }
});
var HelperFuncs = {
  inIframe: () => {
    try {
      return window.self !== window.top;
    } catch (e) {
      return true;
    }
  },

  bodyHasClass: function(arrayOfCssClasses) {
    let bodyClasses = Array.from(document.querySelector('body').classList);
    let intersection = bodyClasses.filter(value => arrayOfCssClasses.includes(value));
    return intersection.length > 0
  }
};
var Home = {
  setInitialStateForShowHideMoreLinks: function() {
    // only show the "Show All" control if there's something more to show
    let panels = document.querySelectorAll('.panel');
    panels.forEach(panel => {
      let showAllControl = panel.querySelector('a.show_all');
      if (Home.hasOverflowHiddenContent(panel)) {
        showAllControl.style.display = 'block';
      } else {
        showAllControl.style.display = 'none';
      }
    });
  },

  addClickListenerToShowHideMoreLinks: function() {
    let showHideMoreLinkControls = document.querySelectorAll('a.show_all');
    showHideMoreLinkControls.forEach(control => {
      control.addEventListener("click", function(e){
        e.preventDefault();
        let controlledPanel = this.closest('div.panel');
        if (Home.hasOverflowHiddenContent(controlledPanel)) { //there are hidden elements to show
          let hiddenElements = $(controlledPanel).find('.home-group-item:hidden');
          $(hiddenElements).addClass('was-hidden').slideDown();
          this.innerHTML = 'Show Fewer';
        } else { // the hidden elements are shown, hide them again
          let shownElements = $(controlledPanel).find('.was-hidden');
          $(shownElements).slideUp();
          this.innerHTML = 'Show All';
        }
      });
    });
  },

  hasOverflowHiddenContent: function(element) {
    return !!$(element).find('.home-group-item:hidden').length;
  }
};

document.addEventListener("DOMContentLoaded", function(){
  if (HelperFuncs.bodyHasClass('home')) {
    Home.setInitialStateForShowHideMoreLinks();
    Home.addClickListenerToShowHideMoreLinks(); 
  }
});
// container for various InPlayer functions
//   we want to hold an InPlayer paywall object instance here for accessibility
//   across the player, but maintain namespacing

var InPlayer = {
  paywall: null
};
/*!
   JW Player version 8.38.8
   Copyright (c) 2025, JW Player, All Rights Reserved
   This source code and its use and distribution is subject to the terms
   and conditions of the applicable license agreement.
   https://www.jwplayer.com/tos/
   This product includes portions of other software. For the full text of licenses, see
   https://ssl.p.jwpcdn.com/player/v/8.38.8/notice.txt
*/(()=>{var e,t,n={696:(e,t,n)=>{"use strict";n.d(t,{Z:()=>r});const r={advertising:{admessage:"This ad will end in xx",cuetext:"Advertisement",displayHeading:"Advertisement",loadingAd:"Loading ad",podmessage:"Ad __AD_POD_CURRENT__ of __AD_POD_LENGTH__.",skipmessage:"Skip ad in xx",skiptext:"Skip"},airplay:"AirPlay",audioTracks:"Audio Tracks",auto:"Auto",buffer:"Loading",cast:"Chromecast",cc:"Closed Captions",close:"Close",errors:{badConnection:"This video cannot be played because of a problem with your internet connection.",cantLoadPlayer:"Sorry, the video player failed to load.",cantPlayInBrowser:"The video cannot be played in this browser.",cantPlayVideo:"This video file cannot be played.",errorCode:"Error Code",liveStreamDown:"The live stream is either down or has ended.",protectedContent:"There was a problem providing access to protected content.",technicalError:"This video cannot be played because of a technical error."},exitFullscreen:"Exit Fullscreen",fullscreen:"Fullscreen",hd:"Quality",liveBroadcast:"Live",logo:"Logo",mute:"Mute",next:"Next",nextUp:"Next Up",notLive:"Not Live",off:"Off",pause:"Pause",pipIcon:"Picture in Picture (PiP)",play:"Play",playback:"Play",playbackRates:"Playback Rates",player:"Video Player",poweredBy:"Powered by",prev:"Previous",related:{autoplaymessage:"Next up in xx",heading:"More Videos"},replay:"Replay",rewind:"Rewind 10 Seconds",settings:"Settings",sharing:{copied:"Copied",email:"Email",embed:"Embed",heading:"Share",link:"Link"},slider:"Seek",stop:"Stop",unmute:"Unmute",videoInfo:"About This Video",volume:"Volume",volumeSlider:"Volume",shortcuts:{playPause:"Play/Pause",volumeToggle:"Mute/Unmute",fullscreenToggle:"Fullscreen/Exit Fullscreen",seekPercent:"Seek %",keyboardShortcuts:"Keyboard Shortcuts",increaseVolume:"Increase Volume",decreaseVolume:"Decrease Volume",seekForward:"Seek Forward",seekBackward:"Seek Backward",spacebar:"SPACE",captionsToggle:"Captions On/Off",shortcutsToggle:"Shortcuts Open/Close"},captionsStyles:{subtitleSettings:"Subtitle Settings",color:"Font Color",fontOpacity:"Font Opacity",userFontScale:"Font Size",fontFamily:"Font Family",edgeStyle:"Character Edge",edgeColor:"Edge Color",backgroundColor:"Background Color",backgroundOpacity:"Background Opacity",windowColor:"Window Color",windowOpacity:"Window Opacity",white:"White",black:"Black",red:"Red",green:"Green",blue:"Blue",yellow:"Yellow",magenta:"Magenta",cyan:"Cyan",none:"None",raised:"Raised",depressed:"Depressed",uniform:"Uniform",dropShadow:"Drop Shadow"},disabled:"Disabled",enabled:"Enabled",reset:"Reset"}},9128:(e,t,n)=>{"use strict";function r(e,t,n){const r=[],u={},i=function(){for(;r.length>0;){const{command:t,args:n}=r.shift();(u[t]||e[t]).apply(e,n)}};t.forEach((t=>{const o=e[t];u[t]=o,e[t]=function(...e){n()?r.push({command:t,args:e}):(i(),o&&o.apply(this,e))}})),Object.defineProperty(this,"queue",{enumerable:!0,get:()=>r}),this.flush=i,this.empty=function(){r.length=0},this.off=function(){t.forEach((t=>{const n=u[t];n&&(e[t]=n,delete u[t])}))},this.destroy=function(){this.off(),this.empty()}}n.d(t,{Z:()=>r})},4742:(e,t,n)=>{"use strict";n.d(t,{Z:()=>r});const r={debug:!1}},5191:(e,t,n)=>{"use strict";n.d(t,{R:()=>u,a:()=>r});const r=function(e){return e.slice&&"px"===e.slice(-2)&&(e=e.slice(0,-2)),e},u=function(e,t){if(-1===t.toString().indexOf("%"))return 0;if("string"!=typeof e||!e)return 0;if(/^\d*\.?\d+%$/.test(e))return e;const n=e.indexOf(":");if(-1===n)return 0;const r=parseFloat(e.substr(0,n)),u=parseFloat(e.substr(n+1));return r<=0||u<=0?0:u/r*100+"%"}},5083:(e,t,n)=>{"use strict";n.d(t,{G0:()=>f,ZP:()=>D,ke:()=>d});var r=n(5191),u=n(1569),i=n(9888),o=n(6042),s=n(8348),a=n(696),c=n(8518),l=function(e,t){if(null==e)throw new TypeError("Cannot convert undefined or null to object");return Object.prototype.hasOwnProperty.call(Object(e),t)};const d={autoPause:{viewability:!1,pauseAds:!1},autostart:!1,allowFullscreen:!0,bandwidthEstimate:null,bitrateSelection:null,castAvailable:!1,controls:!0,cues:[],defaultPlaybackRate:1,displaydescription:!0,displaytitle:!0,displayPlaybackLabel:!1,enableAdLoadingUI:!0,allowPlaybackWhileHiddenAdLoading:!1,enableShortcuts:!0,floating:{mode:"never"},height:360,intl:{},item:0,language:"en",liveTimeout:null,localization:a.Z,mute:!1,nextUpDisplay:!0,playbackRateControls:!1,playbackRates:[.5,1,1.25,1.5,2],renderCaptionsNatively:!1,repeat:!1,showUIWhen:"onReady",stretching:"uniform",volume:90,width:640},f=function(e){return e<5?5:e},D=function(e,t){var D,p;const h={};t&&l(t,"mute")&&("boolean"==typeof t.mute&&(h.mute=t.mute),delete t.mute);const g=Object.assign({},h,null==(D=window)||null==(p=D.jwplayer)?void 0:p.defaults,t,e);!function(e){Object.keys(e).forEach((t=>{"id"!==t&&(e[t]=(0,i.serialize)(e[t]))}))}(g);const m=g.forceLocalizationDefaults?d.language:(0,c.G3)(),y=(0,c.tK)(g.intl);g.localization=(0,c.Mh)(a.Z,(0,c.Pm)(g,y,m));const C=Object.assign({},d,g);"."===C.base&&(C.base=(0,u.getScriptPath)("jwplayer.js")),C.base=(C.base||(0,u.loadFrom)()).replace(/\/?$/,"/"),n.p=C.base,C.width=(0,r.a)(C.width),C.height=(0,r.a)(C.height),C.aspectratio=(0,r.R)(C.aspectratio,C.width),"string"==typeof C.volume&&(C.volume=parseFloat(C.volume)),C.volume=(0,o.qh)(C.volume)?Math.min(Math.max(0,C.volume),100):d.volume,C.mute=Boolean(C.mute),C.language=m,C.intl=y;const F=C.playlistIndex;F&&(C.item=F),(0,o.hj)(C.item)||(C.item=0);const v=g.autoPause;v&&(C.autoPause.viewability=!("viewability"in v)||Boolean(v.viewability));const A=C.playbackRateControls;if(A){let e=C.playbackRates;Array.isArray(A)&&(e=A),e=e.filter((e=>(0,o.hj)(e)&&e>=.25&&e<=4)).map((e=>Math.round(100*e)/100)),e.indexOf(1)<0&&e.push(1),e.sort(),C.playbackRateControls=!0,C.playbackRates=e}(!C.playbackRateControls||C.playbackRates.indexOf(C.defaultPlaybackRate)<0)&&(C.defaultPlaybackRate=1),C.playbackRate=C.defaultPlaybackRate,C.aspectratio||delete C.aspectratio;const E=C.playlist;if(E)Array.isArray(E.playlist)&&(C.feedData=E,C.playlist=E.playlist);else{const e=(0,o.ei)(C,["title","description","type","mediaid","image","images","file","sources","tracks","preload","duration","chapters"]);C.playlist=[e]}C.qualityLabels=C.qualityLabels||C.hlslabels,delete C.duration;let b=C.liveTimeout;null!==b&&((0,o.qh)(b)?0!==b&&(b=Math.max(30,b)):b=null,C.liveTimeout=b);const w=parseFloat(C.bandwidthEstimate),B=parseFloat(C.bitrateSelection);var k;(C.bandwidthEstimate=(0,o.qh)(w)?w:function(e){const t=parseFloat(e);return(0,o.qh)(t)?Math.max(t,1):d.bandwidthEstimate}(C.defaultBandwidthEstimate),C.bitrateSelection=(0,o.qh)(B)?B:d.bitrateSelection,C.liveSyncDuration=f(C.liveSyncDuration),C.backgroundLoading=(0,o.jn)(C.backgroundLoading)?C.backgroundLoading:s.Features.backgroundLoading,C.enableAdLoadingUI=function(e,t,n){return!n.enableAdLoadingUI||(l(e,"enableAdLoadingUI")?Boolean(e.enableAdLoadingUI):!t.dynamicAds)}(g,C,s.Features),!1===C.enableAdLoadingUI)&&(C.backgroundLoading=!0,C.allowPlaybackWhileHiddenAdLoading=null==(k=g.allowPlaybackWhileHiddenAdLoading)||k);return C}},2894:(e,t,n)=>{"use strict";n.d(t,{Ep:()=>o,Jt:()=>s,Tr:()=>i,Zq:()=>a});var r=n(4446);const u=n(8494).Z.logger.child("chunkLoader"),i={},o=function(e,t){return n=>{throw u.error(n),new r.rG(r.pJ,e,t)}},s=function(e,t){return n=>{throw u.warn(n),new r.rG(null,e,t)}},a=function(){return n.e(681).then(function(e){return n(8653).default}.bind(null,n)).catch(o(r.fU+101))}},9750:(e,t,n)=>{"use strict";n.d(t,{ZP:()=>pe,c2:()=>fe});var r=n(9128),u=n(2445),i=n(2894),o=n(393),s=n(8320),a=n(2963),c=n(670),l=n(4601),d=n(4446),f=n(8348);let D=null;const p=function(){const e=window.IntersectionObserverEntry;return!e||!("IntersectionObserver"in window)||!("intersectionRatio"in e.prototype)},h=function(){return(p()?n.e(943).then(function(e){return n(6337)}.bind(null,n)).catch((0,i.Ep)(d.fU+120)):Promise.resolve()).then(i.Zq)},g=function(e){const t=e.get("controls"),r=p(),u=function(e,t){const n=e.get("playlist");if(Array.isArray(n)&&n.length){const r=(0,s.bx)(e.get("item"),n.length),u=(0,s.T5)((0,o.Z)(n[r]),e);for(let n=0;n<u.length;n++){const r=u[n],i=e.getProviders();for(let e=0;e<a.B.length;e++){const n=a.B[e];if(i.providerSupports(n,r))return n.name===t}}}return!1}(e,"html5");return f.OS.tizen?h():t&&r&&u?function(){const e=n.e(605).then(function(e){n(6337);const t=n(8653).default;return l.v.controls=n(1130).default,(0,c.Z)(n(9181).default),t}.bind(null,n)).catch((0,i.Ep)(d.fU+105));return i.Tr.html5=e,e}():t&&u?function(){const e=n.e(207).then(function(e){const t=n(8653).default;return l.v.controls=n(1130).default,(0,c.Z)(n(9181).default),t}.bind(null,n)).catch((0,i.Ep)(d.fU+104));return i.Tr.html5=e,e}():t&&r?n.e(493).then(function(e){n(6337);const t=n(8653).default;return l.v.controls=n(1130).default,t}.bind(null,n)).catch((0,i.Ep)(d.fU+103)):t?n.e(581).then(function(e){const t=n(8653).default;return l.v.controls=n(1130).default,t}.bind(null,n)).catch((0,i.Ep)(d.fU+102)):h()};var m=n(1643),y=n(7263),C=n(676);const F="__JWP____ePBPK____";let v={};window[F]?v=window[F]:window[F]=v;const A={},E={},b=(e,t)=>{const n=v[t];return n||(v[t]=new Promise(((n,r)=>{const u=new e.key(t);if("unlimited"===u.edition())return r();const i=["//","entitlements.jwplayer.com","/",u.token(),".json"];"file:"===window.location.protocol&&i.unshift("https:"),e.ajax(i.join(""),(function(e){const t=null==e?void 0:e.response;t?n(t):r()}),(function(){r()}),{timeout:1e4,responseType:"json"})})))};var w=n(8518),B=n(4425),k=n(8381);const j=function(e,t,n){const r=e.attributes;r.playlist=(0,s.ZP)(t),r.feedData=n},P=(e,t)=>{var n,r;const u=null==(n=t.utils)||null==(r=n.logger)||null==r.child?void 0:r.child("loadIdentity");var i,o;(i=t.utils,o=e.get("key"),A[o]||(A[o]=b(i,o).catch((()=>{throw new Error("Identity Script Disallowed Due to Entitlement Request Error")})).then((e=>{if(!0!==e.canUseIdentityScript)throw new Error("Identity Script Disallowed Due to Missing Entitlement");return{message:"Identity Script Allowed"}})))).then((e=>{if("undefined"!=typeof window&&window.document&&window.document.querySelector('script[src*="connatix.com/identity.js"]'))u.debug("Identity script already on page");else if(e&&"undefined"!=typeof window&&window.document){const e=window.document.createElement("script");e.src="//cd.connatix.com/identity.js",e.setAttribute("async","1"),e.setAttribute("type","text/javascript"),window.document.head.appendChild(e)}})).catch((e=>{null==u||null==u.debug||u.debug(e)}))},S=(e,t)=>{const n=e.get("key"),r=e.get("advertising");return r&&r.adscheduleid?((e,t)=>{const n=E[t];return n||(E[t]=b(e,t).catch((()=>{throw new Error("Override Ad Config Disallowed Due to Entitlement Request Error")})).then((e=>{if(!0!==e.overrideAdConfig)throw new Error("Override Ad Config Disallowed Due to Missing Entitlement");return{message:"Override Ad Config Allowed"}})))})(t.utils,n).then((()=>{const t=Object.assign({client:"cnx",adscheduleid:r.adscheduleid},null!=r&&r.adServer?{adServer:r.adServer}:{});t.overrideAdConfigActive=!0,e.set("advertising",t),e.set("plugins",(0,u.qG)(Object.assign({},e.attributes,{plugins:{}})))})):Promise.resolve()},O=function(e){const t=e.get("playlist");return new Promise(((n,r)=>{if("string"!=typeof t){const r=e.get("feedData")||{};return j(e,t,r),n()}const u=new y.Z;u.on(m.Ow,(function(t){const r=t.playlist;delete t.playlist,j(e,r,t),n()})),u.on(m.pn,(t=>{j(e,[],{}),r((0,d.l9)(t,d.xk))})),u.load(t)}))},x=function(e){return e.attributes._destroyed};var _=n(1918),T=n(6599),I=n(7010);const N=function(e){const t=e.get("skin")?e.get("skin").url:void 0;if("string"==typeof t&&!function(e){const t=document.styleSheets;for(let n=0,r=t.length;n<r;n++)if(t[n].href===e)return!0;return!1}(t)){const e=!0;return new C.ZP(t,e).load().catch((e=>e))}return Promise.resolve()},Z=e=>{const t=e.get("advertising");return Boolean(null==t?void 0:t.outstream)},L=e=>Z(e)?Promise.resolve():O(e).then((()=>{if(e.get("drm")||(0,_.w0)(e.get("playlist")))return(0,_.lD)(e.get("edition"))})).then((()=>{return O(t=e).then((()=>{if(x(t))return;const e=(0,s.s7)(t.get("playlist"),t);t.attributes.playlist=e;try{(0,s._)(e)}catch(e){throw e.code+=d.xk,e}const n=t.getProviders(),r=(0,s.bx)(t.get("item"),e.length),{provider:u,name:o}=n.choose(e[r].sources[0]);return"function"==typeof u?u:i.Tr.html5&&"html5"===o?i.Tr.html5:n.load(o).catch((e=>{throw(0,d.l9)(e,d.y4)}))}));var t})),M=e=>{const t=e.attributes,n=t.error;if(n&&n.code===T.u5){const e=t.pid,n=t.ph,r=new T.ZP(t.key),u=7776e6;if(n>0&&n<4&&e&&r.duration()>-u){return new C.ZP(`//content.jwplatform.com/libraries/${e}.js`).load().then((()=>{const e=window.jwplayer.defaults.key,n=new T.ZP(e);n.error()||n.token()!==r.token()||(t.key=e,t.edition=n.edition(),t.error=n.error())})).catch((()=>{}))}}return Promise.resolve()},$=(e,t)=>{const n=[M(e)];return Z(e)||n.push(Promise.resolve()),Promise.all(n)},R=(e,t)=>function(e,t){return n.e(168).then((r=>new(0,n(5545).default)(t).setup(e)).bind(null,n)).catch((0,i.Ep)(d.fU+130))}(e,t).then((()=>N(e))),U=(e,t)=>{const n=()=>function(e,t){return(0,B.ZP)(e,t)}(e,t);return(0,I.Z)()?R(e,t).then(n).catch(n):n()},z=function(e){const{attributes:t}=e,{language:n,base:r,setupConfig:u,intl:i}=t,o=(0,w.Pm)(u,i,n);return!(0,w.q2)(n)||(0,w.dl)(o)?Promise.resolve():new Promise((u=>(0,w.Dq)(r,n).then((({response:n})=>{if(!x(e)){if(!n)throw new d.rG(null,d.wH);t.localization=(0,w.Mh)(n,o),u()}})).catch((e=>{u(e.code===d.wH?e:(0,d.l9)(e,d.A6))}))))},q=e=>new Promise((t=>{if(e.attributes.liveSyncDuration>45)return t((0,d.l9)(new Error,d.wM));const n=Array.isArray(e.attributes.playlist)&&e.attributes.playlist.map((e=>e.chapters));return null!=n&&n.length?(0,k.T2)(n,t):t()})),V=async(e,t)=>{try{P(e,t)}catch(e){}try{await S(e,t)}catch(e){}};var H=n(7642);const G=function(e){let t;this.start=function(n){let r;const u=V(e,n).then((()=>{r=U(e,n);const t=(0,H.k)(e,n);var u;return Promise.all([(u=e,D||(D=g(u)),D),q(e),r,t,L(e),$(e),N(e),z(e)])})),i=new Promise(((e,n)=>{t=setTimeout((()=>{n(new d.rG(d.pJ,d.T6))}),6e4);const r=()=>{clearTimeout(t),setTimeout(e,6e4)};u.then(r).catch(r)}));return Promise.race([u,i]).catch((e=>{const t=()=>{throw e};return r?r.then(t).catch(t):t()})).then((e=>function(e){if(!e||!e.length)return{core:null,warnings:[]};const t=e.reduce(((e,t)=>e.concat(t)),[]).filter((e=>null==e?void 0:e.code));return{core:e[0],warnings:t}}(e)))},this.destroy=function(){clearTimeout(t),e.set("_destroyed",!0),e=null}};var K=n(2303),W=n(7411),Q=n(9888),J=n(4742),X=n(8494);const Y=X.Z.logger.child("jwplayer/model/storage");let ee={removeItem(e){}};try{ee=window.localStorage||ee}catch(e){Y.debug(e)}const te=class{constructor(e,t){this.namespace=e,this.items=t}getAllItems(){return this.items.reduce(((e,t)=>{const n=ee[`${this.namespace}.${t}`];return n&&(e[t]="captions"!==t?(0,Q.serialize)(n):JSON.parse(n)),e}),{})}track(e){this.items.forEach((t=>{e.on(`change:${t}`,((e,n)=>{try{"captions"===t&&(n=JSON.stringify(n)),ee[`${this.namespace}.${t}`]=n}catch(e){J.Z.debug&&Y.error(e)}}))}))}clear(){this.items.forEach((e=>{ee.removeItem(`${this.namespace}.${e}`)}))}};var ne=n(7753),re=n(9918),ue=n(328),ie=n(4225),oe=n(7683),se=n(4609),ae=n(5882);n(4671),n(9926);const ce=X.Z.logger.child("jwplayer/api/core-shim"),le=function(e,t){t&&t.code&&(t.sourceError&&ce.error(t.sourceError),ce.error(d.rG.logMessage(t.code)))},de=function(e){e&&e.code&&ce.warn(d.rG.logMessage(e.code))},fe=function(e,t){if(!document.body.contains(e.currentContainer)){const t=document.getElementById(e.get("id"));t&&(e.currentContainer=t)}e.currentContainer.parentElement&&e.currentContainer.parentElement.replaceChild(t,e.currentContainer),e.currentContainer=t},De=function(e){this._events={},this.modelShim=new ne.Z,this.modelShim._qoeItem=new W.Z,this.mediaShim={},this.setup=new G(this.modelShim),this.currentContainer=this.originalContainer=e,this.apiQueue=new r.Z(this,["load","play","pause","seek","stop","playlistItem","playlistNext","playlistPrev","next","preload","setAllowFullscreen","setConfig","setCurrentAudioTrack","setCurrentCaptions","setCurrentQuality","setFullscreen","setPip","requestPip","addButton","removeButton","castToggle","requestCast","setMute","setVolume","setPlaybackRate","addCues","setCues","getCues","setPlaylistItem","stopCasting","getChapters","getCurrentChapter","setChapter","resize","setCaptions","setControls"],(()=>!0))};Object.assign(De.prototype,{on:ue.ZP.on,once:ue.ZP.once,off:ue.ZP.off,trigger:ue.ZP.trigger,init(e,t){const n=this.modelShim,r=new te("jwplayer",["volume","mute","captionLabel","captions","bandwidthEstimate","bitrateSelection","qualityLabel","enableShortcuts"]),i=null==r?void 0:r.getAllItems();n.attributes=n.attributes||{},Object.assign(this.mediaShim,re.L4);const o=e,s=(0,u.ZP)(Object.assign({},e),i);s.id=t.id,s.setupConfig=o,Object.assign(n.attributes,s,re.bv),n.getProviders=function(){return new K.Z(s)},n.setProvider=function(){};let a=(0,oe.Z)();{n.get("backgroundLoading")||(a=(0,se.Z)(a.getPrimedElement(),a));const e=this.primeUi=new ae.ZP((0,ae.GU)(this.originalContainer)).once("gesture",(()=>{a.prime(),this.preload(),e.destroy()}))}return n.on("change:errorEvent",le),this.setup.start(t).then((e=>{const u=e.core;if(!u)throw(0,d.l9)(null,d.y7);if(!this.setup)return;this.on(m.cM,de),e.warnings.forEach((e=>{this.trigger(m.cM,e)}));const i=this.modelShim.clone();if(i.error)throw i.error;const o=this.apiQueue.queue.slice(0);this.apiQueue.destroy(),Object.assign(this,u.prototype),this.playerSetup(i,t,this.originalContainer,this._events,o,a);const s=this._model;return n.off("change:errorEvent",le),s.on("change:errorEvent",le),r.track(s),this.updatePlaylist(s.get("playlist"),s.get("feedData")).catch((e=>{const t=e.code===d._M?d.IB:d.xk;throw(0,d.l9)(e,t)}))})).then((()=>{this.setup&&this.playerReady()})).catch((e=>{this.setup&&function(e,t,n){Promise.resolve().then((()=>{const r=(0,d.Mm)(d.ud,d.nk,n),u=e._model||e.modelShim;r.message=r.message||u.get("localization").errors[r.key],delete r.key;const i=u.get("contextual");if(!i){const t=(0,ie.Z)(e,r);ie.Z.cloneIcon&&t.querySelector(".jw-icon").appendChild(ie.Z.cloneIcon("error")),fe(e,t)}u.set("errorEvent",r),u.set("state",m.Vy),e.trigger(m.HH,r),i&&t.remove()}))}(this,t,e)}))},playerDestroy(){this.destroy&&this.destroy(),this.apiQueue&&this.apiQueue.destroy(),this.setup&&this.setup.destroy(),this.primeUi&&this.primeUi.destroy(),this.currentContainer!==this.originalContainer&&fe(this,this.originalContainer),this.off(),this._events=this._model=this.modelShim=this.apiQueue=this.primeUi=this.setup=null},getContainer(){return this.currentContainer},get(e){if(this.modelShim)return e in this.mediaShim?this.mediaShim[e]:this.modelShim.get(e)},getItemQoe(){return this.modelShim._qoeItem},getItemPromise:()=>null,setItemCallback(e){this.modelShim&&(this.modelShim.attributes.playlistItemCallback=e)},getConfig(){return Object.assign({},this.modelShim.attributes,this.mediaShim)},getCurrentCaptions(){return this.get("captionsIndex")},getWidth(){return this.get("containerWidth")},getHeight(){return this.get("containerHeight")},getMute(){return this.get("mute")},getProvider(){return this.get("provider")},getState(){return this.get("state")},getAbsolutePosition:()=>null,getAudioTracks:()=>null,getCaptionsList:()=>null,getQualityLevels:()=>null,getVisualQuality:()=>null,getCurrentQuality:()=>-1,getCurrentAudioTrack:()=>-1,getSafeRegion:()=>({x:0,y:0,width:0,height:0}),isBeforeComplete:()=>!1,isBeforePlay:()=>!1,createInstream:()=>null,skipAd(){},getMediaElement(){},attachMedia(){},detachMedia(){},isReady(){var e;return(null==(e=this._model)?void 0:e.get("isReady"))||!1}});const pe=De},4446:(e,t,n)=>{"use strict";n.d(t,{A6:()=>F,DD:()=>d,EY:()=>g,H4:()=>k,IB:()=>c,MD:()=>E,Mm:()=>S,Sp:()=>B,T6:()=>i,Y7:()=>C,YQ:()=>l,_M:()=>h,aD:()=>y,fU:()=>s,l9:()=>O,nk:()=>u,nm:()=>x,o2:()=>p,pJ:()=>b,rG:()=>P,tJ:()=>D,ud:()=>j,ul:()=>A,wH:()=>v,wM:()=>m,xk:()=>a,y4:()=>f,y7:()=>o,zO:()=>w});var r=n(6042);const u=1e5,i=100001,o=100002,s=101e3,a=102e3,c=102700,l=200001,d=202e3,f=104e3,D=203e3,p=203640,h=203700,g=204e3,m=300100,y=300200,C=306e3,F=308e3,v=308640,A="cantPlayVideo",E="badConnection",b="cantLoadPlayer",w="cantPlayInBrowser",B="liveStreamDown",k="protectedContent",j="technicalError";class P{constructor(e,t,n){this.code=(0,r.qh)(t)?t:0,this.sourceError=n||null,e?this.key=e:delete this.key}static logMessage(e){const t=e%1e3,n=Math.floor((e-t)/1e3);let r=e.toString();t>=400&&t<600&&(r=`${n}400-${n}599`);return`JW Player ${e>299999&&e<4e5?"Warning":"Error"} ${e}. For more information see https://developer.jwplayer.com/jw-player/docs/developer-guide/api/errors-reference#${r}`}}const S=function(e,t,n){return n instanceof P&&n.code?n:new P(e,t,n)},O=function(e,t){const n=S(j,t,e);return n.code=(e&&e instanceof P&&e.code||0)+t,n},x=function(e){const{name:t,message:n}=e;switch(t){case"AbortError":return/pause/.test(n)?303213:/load/.test(n)?303212:303210;case"NotAllowedError":return 303220;case"NotSupportedError":return 303230;default:return 303200}}},6391:(e,t,n)=>{"use strict";n.d(t,{Z:()=>r});const r=[]},7411:(e,t,n)=>{"use strict";n.d(t,{Z:()=>a});var r=n(5004);const u=window.performance||{timing:{}},i=u.timing.navigationStart||(0,r.z)();"now"in u||(u.now=()=>(0,r.z)()-i);const o=()=>i+u.now();var s=function(e,t){if(null==e)throw new TypeError("Cannot convert undefined or null to object");return Object.prototype.hasOwnProperty.call(Object(e),t)};const a=class{constructor(){this.startTimes={},this.sum={},this.counts={},this.ticks={}}start(e){this.startTimes[e]=o(),this.counts[e]=this.counts[e]+1||1}end(e){if(!this.startTimes[e])return;const t=o()-this.startTimes[e];delete this.startTimes[e],this.sum[e]=this.sum[e]+t||t}dump(){const e=Object.assign({},this.sum);for(const t in this.startTimes)if(s(this.startTimes,t)){const n=o()-this.startTimes[t];e[t]=e[t]+n||n}return{counts:Object.assign({},this.counts),sums:e,events:Object.assign({},this.ticks)}}tick(e){this.ticks[e]=o()}clear(e){delete this.ticks[e]}between(e,t){return this.ticks[t]&&this.ticks[e]?this.ticks[t]-this.ticks[e]:null}}},4601:(e,t,n)=>{"use strict";n.d(t,{v:()=>o,z:()=>s});var r=n(2894),u=n(8348);let i=null;const o={},s=function(){return i||(i=u.OS.tizenApp?n.e(74).then(function(e){const t=n(3112).default;return o.controls=t,t}.bind(null,n)).catch((function(){i=null,(0,r.Jt)(301133)()})):n.e(716).then(function(e){const t=n(1130).default;return o.controls=t,t}.bind(null,n)).catch((function(){i=null,(0,r.Jt)(301130)()}))),i}},8348:(e,t,n)=>{"use strict";n.r(t),n.d(t,{Browser:()=>a,Features:()=>l,OS:()=>c});var r=n(2268);const u=(e,t)=>{const n=e.exec(t);if(n&&n.length>1)return n[1]};var i=n(8494);const o=navigator.userAgent,s=()=>{},a={get androidNative(){return(0,r.O7)()},get chrome(){return(0,r.i7)()},get edge(){return(0,r.un)()},get facebook(){return(0,r.DF)()},get firefox(){return(0,r.pZ)()},get ie(){return(0,r.w1)()},get msie(){return(0,r.A)()},get safari(){return(0,r.G6)()},get version(){return((e,t)=>{let n,r,u,i;if(e.chrome)n=-1!==t.indexOf("Chrome")?t.substring(t.indexOf("Chrome")+7):t.substring(t.indexOf("CriOS")+6);else if(e.safari)n=t.substring(t.indexOf("Version")+8);else if(e.firefox)n=t.substring(t.indexOf("Firefox")+8);else if(e.edge){let e=t.indexOf("Edge");-1===e?e=t.indexOf("Edg")+4:e+=5,n=t.substring(e)}else e.ie&&(-1!==t.indexOf("rv:")?n=t.substring(t.indexOf("rv:")+3):-1!==t.indexOf("MSIE")&&(n=t.substring(t.indexOf("MSIE")+5)));return n&&(-1!==(i=n.indexOf(";"))&&(n=n.substring(0,i)),-1!==(i=n.indexOf(" "))&&(n=n.substring(0,i)),-1!==(i=n.indexOf(")"))&&(n=n.substring(0,i)),r=parseInt(n,10),u=parseInt(n.split(".")[1],10)),{version:n,major:r,minor:u}})(this,o)}},c={get android(){return(0,r.Dt)()},get iOS(){return(0,r.gn)()},get mobile(){return(0,r.tq)()},get mac(){return(0,r.id)()},get iPad(){return(0,r.zc)()},get iPhone(){return(0,r.xb)()},get windows(){return o.indexOf("Windows")>-1},get tizen(){return(0,r.yS)()},get tizenApp(){return(0,r.Q6)()},get version(){return((e,t)=>{let n,r,i;if(e.windows)switch(n=u(/Windows(?: NT|)? ([._\d]+)/,t),n){case"6.1":n="7.0";break;case"6.2":n="8.0";break;case"6.3":n="8.1"}else e.android?n=u(/Android ([._\d]+)/,t):e.iOS?n=u(/OS ([._\d]+)/,t):e.mac?n=u(/Mac OS X ([._\d]+)/,t):e.tizen&&(n=u(/Tizen ([._\d]+)/,t));if(n){r=parseInt(n,10);const e=n.split(/[._]/);e&&(i=parseInt(e[1],10))}return{version:n,major:r,minor:i}})(this,o)}},l={get flash(){return(0,r.NO)()},get flashVersion(){return(0,r.dI)()},get iframe(){return(0,r.cL)()},get passiveEvents(){return(()=>{let e=!1;try{const t=Object.defineProperty({},"passive",{get:()=>e=!0});window.addEventListener("testPassive",s,t),window.removeEventListener("testPassive",s,t)}catch(e){i.Z.logger.child("jwplayer/environment/environment").debug(e)}return e})()},get backgroundLoading(){return!(c.iOS||c.tizen)},get headless(){return!1},get enableAdLoadingUI(){return!c.tizen}}},1643:(e,t,n)=>{"use strict";n.d(t,{$_:()=>E,$j:()=>x,AQ:()=>I,Ax:()=>b,B1:()=>g,Bs:()=>Ce,Ew:()=>M,FU:()=>$,Gj:()=>ge,HH:()=>q,Hy:()=>re,Ib:()=>De,Je:()=>U,Jl:()=>T,K5:()=>y,Kb:()=>r,Ms:()=>P,NZ:()=>O,O1:()=>X,Ow:()=>se,P:()=>h,QF:()=>fe,R2:()=>G,RF:()=>Ae,Rc:()=>S,Rt:()=>A,SL:()=>pe,Sv:()=>D,TJ:()=>K,U3:()=>C,UF:()=>de,UW:()=>ue,UZ:()=>ee,V$:()=>Z,Vy:()=>a,WE:()=>w,Wp:()=>d,Z_:()=>he,_5:()=>o,_B:()=>ce,aM:()=>te,aQ:()=>z,bc:()=>u,cM:()=>v,cq:()=>R,cy:()=>N,gO:()=>oe,gy:()=>J,h7:()=>Fe,ik:()=>c,j0:()=>ae,jt:()=>le,k3:()=>B,l5:()=>ye,nQ:()=>l,nv:()=>f,oZ:()=>W,ot:()=>p,pi:()=>L,pn:()=>F,qG:()=>ve,r0:()=>s,rx:()=>Y,s$:()=>_,sF:()=>ie,t6:()=>Ee,tP:()=>m,uL:()=>k,uT:()=>H,uc:()=>V,ug:()=>ne,wh:()=>j,xQ:()=>i,xf:()=>me,yH:()=>Q,zs:()=>be});const r="buffering",u="idle",i="complete",o="paused",s="playing",a="error",c="loading",l="stalled",d="drag",f="dragStart",D="dragEnd",p="click",h="doubleClick",g="over",m="move",y="enter",C="out",F=a,v="warning",A="adClick",E="mediaLoaded",b="adPause",w="adPlay",B="adSkipped",k="adTime",j="autostartNotAllowed",P=i,S="ready",O="seek",x="beforePlay",_="beforeComplete",T="bufferFull",I="absolutePositionReady",N="displayClick",Z="playlistComplete",L="cast",M="mediaError",$="firstFrame",R="playAttempt",U="playAttemptFailed",z="seeked",q="setupError",V="state",H="bufferChange",G="time",K="ratechange",W="mediaType",Q="volume",J="mute",X="metadataCueParsed",Y="meta",ee="levels",te="levelsChanged",ne="visualQuality",re="controls",ue="fullscreen",ie="resize",oe="playlistItem",se="playlist",ae="audioTracks",ce="audioTrackChanged",le="subtitlesTracks",de="subtitlesTrackChanged",fe="playbackRateChanged",De="logoClick",pe="captionsList",he="captionsChanged",ge="providerFirstFrame",me="userAction",ye="instreamClick",Ce="breakpoint",Fe="fullscreenchange",ve="bandwidthEstimate",Ae="float",Ee="chapter",be="mediaCueChanged"},9918:(e,t,n)=>{"use strict";n.d(t,{L4:()=>u,OG:()=>o,bv:()=>r,ni:()=>i});const r={audioMode:!1,itemMeta:{},playbackRate:1,playRejected:!1,state:n(1643).bc,itemReady:!1,controlsEnabled:!1},u={position:0,duration:0,buffer:0,currentTime:0},i=120,o=25},7753:(e,t,n)=>{"use strict";n.d(t,{Z:()=>u});var r=n(328);class u extends r.ZP{constructor(){super(),this.attributes=Object.create(null)}addAttributes(e){Object.keys(e).forEach((t=>{this.add(t,e[t])}))}add(e,t){Object.defineProperty(this,e,{get:()=>this.attributes[e],set:t=>{this.set(e,t)},enumerable:!1}),this.attributes[e]=t}get(e){return this.attributes[e]}set(e,t){if(this.attributes[e]===t)return;const n=this.attributes[e];this.attributes[e]=t,this.trigger(`change:${e}`,this,t,n)}clone(){const e={},t=this.attributes;if(t)for(const n in t)e[n]=t[n];return e}change(e,t,n){this.on(`change:${e}`,t,n);const r=this.get(e);return t.call(n,this,r,r),this}}},7941:(e,t,n)=>{"use strict";n.d(t,{dZ:()=>i,my:()=>s,qk:()=>o,r1:()=>u});var r=n(2957);const u=e=>{let t="";return e&&(e.localName?t=e.localName:e.baseName&&(t=e.baseName)),t},i=e=>{let t="";return e&&(e.textContent?t=(0,r.fy)(e.textContent):e.text&&(t=(0,r.fy)(e.text))),t},o=(e,t)=>e.childNodes[t],s=e=>e.childNodes?e.childNodes.length:0},6769:(e,t,n)=>{"use strict";n.d(t,{Z:()=>D});var r=n(7941),u=n(2957);const i=e=>{const t=[];for(let n=0;n<(0,r.my)(e);n++){const u=e.childNodes[n];"jwplayer"===u.prefix&&"mediatypes"===(0,r.r1)(u).toLowerCase()&&t.push((0,r.dZ)(u))}return t},o=e=>{const t={zh:"Chinese",nl:"Dutch",en:"English",fr:"French",de:"German",it:"Italian",ja:"Japanese",pt:"Portuguese",ru:"Russian",es:"Spanish"};return t[e]?t[e]:e},s=function(e,t){const n=[];for(let a=0;a<(0,r.my)(e);a++){const c=e.childNodes[a];if("media"===c.prefix){if(!(0,r.r1)(c))continue;switch((0,r.r1)(c).toLowerCase()){case"content":if((0,u.Dc)(c,"duration")&&(t.duration=(0,u.m9)((0,u.Dc)(c,"duration"))),(0,u.Dc)(c,"url")){t.sources||(t.sources=[]);const e={file:(0,u.Dc)(c,"url"),type:(0,u.Dc)(c,"type"),width:(0,u.Dc)(c,"width"),label:(0,u.Dc)(c,"label")},n=i(c);n.length&&(e.mediaTypes=n),t.sources.push(e)}(0,r.my)(c)>0&&(t=s(c,t));break;case"title":t.title=(0,r.dZ)(c);break;case"description":t.description=(0,r.dZ)(c);break;case"guid":t.mediaid=(0,r.dZ)(c);break;case"thumbnail":t.image||(t.image=(0,u.Dc)(c,"url"));break;case"group":s(c,t);break;case"subtitle":{const e={file:(0,u.Dc)(c,"url"),kind:"captions"};(0,u.Dc)(c,"lang").length>0&&(e.label=o((0,u.Dc)(c,"lang"))),n.push(e);break}}}}t.tracks||(t.tracks=[]);for(let e=0;e<n.length;e++)t.tracks.push(n[e]);return t},a=s;var c=n(9888);const l=function(e,t){const n="default",i="label",o="file",s=[],a=[],l=t;for(let l=0;l<e.childNodes.length;l++){const d=e.childNodes[l];if("jwplayer"===d.prefix){const e=(0,r.r1)(d);"source"===e?(delete t.sources,s.push({file:(0,u.Dc)(d,o),default:(0,u.Dc)(d,n),label:(0,u.Dc)(d,i),type:(0,u.Dc)(d,"type")})):"track"===e?(delete t.tracks,a.push({file:(0,u.Dc)(d,o),default:(0,u.Dc)(d,n),kind:(0,u.Dc)(d,"kind"),label:(0,u.Dc)(d,i)})):(t[e]=(0,c.serialize)((0,r.dZ)(d)),"file"===e&&t.sources&&delete t.sources)}t[o]||(t[o]=t.link)}if(s.length){t.sources=[];for(let e=0;e<s.length;e++){const t=s[e];t.file.length>0&&(t[n]="true"===s[e][n],t.label||delete t.label,l.sources.push(t))}}if(a.length){t.tracks=[];for(let e=0;e<a.length;e++){const t=a[e];t.file&&t.file.length>0&&(t[n]="true"===a[e][n],t.kind=a[e].kind.length?a[e].kind:"captions",t.label||delete t.label,l.tracks.push(t))}}return l};var d=n(393);const f=e=>{const t={};for(let n=0;n<e.childNodes.length;n++){const i=e.childNodes[n],o=(0,r.r1)(i);if(o)switch(o.toLowerCase()){case"enclosure":t.file=(0,u.Dc)(i,"url");break;case"title":t.title=(0,r.dZ)(i);break;case"guid":t.mediaid=(0,r.dZ)(i);break;case"pubdate":t.date=(0,r.dZ)(i);break;case"description":t.description=(0,r.dZ)(i);break;case"link":t.link=(0,r.dZ)(i);break;case"category":t.tags?t.tags+=(0,r.dZ)(i):t.tags=(0,r.dZ)(i)}}return new d.Z(l(e,a(e,t)))};function D(e){const t=[];t.feedData={};for(let n=0;n<(0,r.my)(e);n++){const u=(0,r.qk)(e,n);if("channel"===(0,r.r1)(u).toLowerCase())for(let e=0;e<(0,r.my)(u);e++){const n=(0,r.qk)(u,e),i=(0,r.r1)(n).toLowerCase();"item"===i?t.push(f(n)):i&&(t.feedData[i]=(0,r.dZ)(n))}}return t}},2557:(e,t,n)=>{"use strict";n.d(t,{t:()=>r,u:()=>u});class r{constructor(e,t){this.defaultLanguage=e,this.timestamps=t}}class u{constructor({title:e={},group:t,time:n,image:r}){this.title={},this.time=n,this.group=t,this.image=r,Object.keys(e).forEach((t=>{const n=e[t];this.addTitle(t,n)}))}addTitle(e,t){this.title[e]=t}}},393:(e,t,n)=>{"use strict";n.d(t,{Z:()=>a});var r=n(6053);const u=["captions","metadata","thumbnails","chapters"],i=function(e){if(!e||!e.file)return;const t=Object.assign({},{kind:"captions",default:!1},e);var n;return t.kind=(n=t.kind,-1!==u.indexOf(n)?t.kind:"captions"),t.default=Boolean(t.default),t};var o=n(9918);const s=Array.isArray,a=function(e){s((e=e||{}).tracks)||delete e.tracks;const t=Object.assign({},{sources:[],tracks:[],minDvrWindow:o.ni},e);t.sources!==Object(t.sources)||s(t.sources)||(t.sources=[(0,r.Z)(t.sources)]),s(t.sources)&&0!==t.sources.length||(e.levels?t.sources=e.levels:t.sources=[(0,r.Z)(e)]);for(let e=0;e<t.sources.length;e++){const n=t.sources[e];if(!n)continue;const u=n.default;n.default=!!u&&"true"===u.toString(),t.sources[e].label||(t.sources[e].label=e.toString()),t.sources[e]=(0,r.Z)(t.sources[e])}return t.sources=t.sources.filter(Boolean),s(t.tracks)||(t.tracks=[]),s(t.captions)&&(t.tracks=t.tracks.concat(t.captions),delete t.captions),t.tracks=t.tracks.map(i).filter(Boolean),t}},7263:(e,t,n)=>{"use strict";n.d(t,{Z:()=>c});var r=n(1643),u=n(7941),i=n(6769),o=n(6886),s=n(328),a=n(4446);const c=function(){const e=Object.assign(this,s.ZP),t=function(t){t instanceof a.rG&&!t.code&&(t=new a.rG(a.ul,0)),e.trigger(r.pn,t)},n=function(n){try{const t=n.responseXML?n.responseXML.childNodes:null;let o,s=null;if(t){for(let e=0;e<t.length&&(s=t[e],8===s.nodeType);e++);if(s&&"xml"===(0,u.r1)(s)&&(s=s.nextSibling),s&&"rss"===(0,u.r1)(s)){const e=(0,i.Z)(s);o=Object.assign({playlist:e},e.feedData)}}if(!o)try{const e=JSON.parse(n.responseText);if(Array.isArray(e))o={playlist:e};else{if(!Array.isArray(e.playlist))throw Error("Playlist is not an array");o=e}}catch(e){throw new a.rG(a.ul,621,e)}e.trigger(r.Ow,o)}catch(e){t(e)}};this.load=function(e){(0,o.h)(e,n,((e,n,r,u)=>{t(u)}))},this.destroy=function(){this.off()}}},8320:(e,t,n)=>{"use strict";n.d(t,{ZP:()=>F,s7:()=>g,T5:()=>C,YF:()=>h,_:()=>m,bx:()=>y});const r={none:!0,metadata:!0,auto:!0},u=(e,t)=>r[e]?e:r[t]?t:"metadata";var i=n(393),o=n(6053),s=n(2303),a=n(4446),c=n(8348);const l=(e,t)=>void 0===e?t:e,d=(e,t,n)=>{n in t&&(e[n]=t[n])},f=(e,t)=>{const{attributes:n}=t,{sources:r,allSources:i,preload:s,drm:a}=e,c=l(e.withCredentials,n.withCredentials);return(i||r).map((function(t){if(t!==Object(t))return null;d(t,n,"androidhls"),d(t,n,"hlsjsdefault"),d(t,n,"safarihlsjs"),((e,t,n)=>{if(e.liveSyncDuration)return;const r=t.liveSyncDuration?t:n;d(e,r,"liveSyncDuration")})(t,e,n),d(t,n,"_hlsjsProgressive"),t.preload=u(t.preload,s);const r=t.drm||a||n.drm;r&&(t.drm=r);const i=l(t.withCredentials,c);return void 0!==i&&(t.withCredentials=i),(0,o.Z)(t)})).filter(Boolean)},D=e=>c.Browser.safari?e.sort((e=>"hls"===e.type?-1:0)):e,p=(e,t)=>{t&&t.choose||(t=new s.Z);const n=((e,t)=>{for(let n=0;n<e.length;n++){const r=e[n],{providerToCheck:u}=t.choose(r);if(u)return{type:r.type,provider:u}}return null})(e,t);if(!n)return[];const r=n.provider,u=n.type;return e.filter((function(e){return e.type===u&&t.providerSupports(r,e)}))},h=(e,t,n)=>{const r=e.getProviders(),i=e.get("preload"),o=e.get("jwStart"),s=Object.assign({},t);if(s.preload=u(t.preload,i),s.allSources=D(f(s,e)),s.sources=p(s.allSources,r),s.sources.length)return s.file=s.sources[0].file,s.feedData=n,o&&-1!==o&&e.get("generateSEOMetadata")&&(s.starttime=o),(e=>{const t=e.sources[0].liveSyncDuration;return t&&(e.liveSyncDuration=e.dvrSeekLimit=t),e})(s)},g=(e,t,n)=>{const r=Object.assign({},n);return delete r.playlist,e.map((e=>h(t,e,r))).filter(Boolean)},m=e=>{if(!Array.isArray(e)||0===e.length)throw new a.rG(a.ul,630)},y=(e,t)=>{let n=(parseInt(e,10)||0)%t;return n<0&&(n+=t),n},C=(e,t)=>p(D(f(e,t)),t.getProviders()),F=function(e){return(Array.isArray(e)?e:[e]).map(i.Z)}},6053:(e,t,n)=>{"use strict";n.d(t,{Z:()=>i});var r=n(7034),u=n(2957);const i=function(e){if(!e||!e.file)return;const t=Object.assign({},{default:!1,type:""},e);t.file=(0,u.fy)(`${t.file}`);const n=/^[^/]+\/(?:x-)?([^/]+)$/,i=t.type;if(n.test(i)&&(t.mimeType=i,t.type=i.replace(n,"$1")),(0,r.isYouTube)(t.file)?t.type="youtube":(0,r.isRtmp)(t.file)?t.type="rtmp":t.type||(t.type=(0,u.AO)(t.file)),t.type){switch(t.type){case"m3u8":case"vnd.apple.mpegurl":t.type="hls";break;case"dash+xml":t.type="dash";break;case"m4a":t.type="aac";break;case"smil":t.type="rtmp"}return Object.keys(t).forEach((function(e){""===t[e]&&delete t[e]})),t}}},4101:(e,t,n)=>{"use strict";n.d(t,{Z:()=>l});var r=n(676),u=n(9888),i=n(2957),o=n(4446),s=n(3487);const a=function(e){if("string"!=typeof e)return;const t=(e=e.split("?")[0]).indexOf("://");if(t>0)return 0;const n=e.indexOf("/"),r=(0,i.AO)(e);return!(t<0&&n<0)||r&&isNaN(r)?1:2},c=function(e){this.url=e,this.promise_=null};Object.defineProperties(c.prototype,{promise:{get(){return this.load()},set(){}}}),Object.assign(c.prototype,{load(){let e=this.promise_;if(!e){if(2===a(this.url))return Promise.resolve(this);const t=new r.ZP((e=>{switch(a(e)){case 0:return e;case 1:return(0,u.getAbsolutePath)(e,window.location.href)}})(this.url));this.loader=t,e=t.load().then((()=>this)),this.promise_=e}return e},registerPlugin(e,t,n){this.name=e,this.target=t,this.js=n},getNewInstance(e,t,n){const r=this.js;if("function"!=typeof r)throw new o.rG(null,(0,s.bX)(this.url)+100);const u=new r(e,t,n);const i={type:"pluginInitialized",name:this.name,config:t};return u.addToPlayer=function(e=!1){const t=this.getContainer().querySelector(".jw-overlays");if(t)return n.left=t.style.left,n.top=t.style.top,t.appendChild(n),e?this.trigger("pluginInitialized",i):setTimeout((()=>this.trigger("pluginInitialized",i)),0),u},u.resizeHandler=function(){const e=this.getContainer().querySelector(".jw-overlays");e&&u.resize(e.clientWidth,e.clientHeight)},u}});const l=c},7164:(e,t,n)=>{"use strict";n.d(t,{MK:()=>o,Nq:()=>u,bX:()=>i});var r=n(5950);const u=function(e){const t=/\/((.(?!\/))+?)\.js/i.exec(e),n=(null==t?void 0:t[1])||e;return n&&"jwpsrv-dnt"===n?"jwpsrv":n},i=e=>305e3,o=(e,t,n)=>{const u=e.name;const i=Object.assign({},t,(0,r.vl)(e.url)),o=document.createElement("div");o.id=`${n.id}_${u}`,o.className="jw-plugin jw-reset";const s=e.getNewInstance(n,i,o);return n.addPlugin(u,s),s}},7683:(e,t,n)=>{"use strict";n.d(t,{V:()=>o,Z:()=>s});var r=n(658);const u=n(8494).Z.logger.child("jwplayer/program/media-element-pool"),i=e=>{e.src||e.load()},o=e=>{const t=document.createElement("video");return t.className="jw-video jw-reset",t.setAttribute("tabindex","-1"),t.setAttribute("disableRemotePlayback",""),t.setAttribute("webkit-playsinline",""),t.setAttribute("playsinline",""),e&&Object.keys(e).forEach((n=>{t.setAttribute(n,e[n])})),t};function s(){const e=r.Jx,t=[],n=[];for(let r=0;r<e;r++){const e=o();t.push(e),n.push(e),i(e)}const s=n.shift(),a=n.shift();let c=!1;return{primed:()=>c,prime(){t.forEach(i),c=!0},played(){c=!0},getPrimedElement:()=>n.shift()||null,getAdElement:()=>s,getTestElement:()=>a,clean(e){if(e.src){e.removeAttribute("src");try{e.load()}catch(e){u.debug(e)}}},recycle(e){e&&!n.some((t=>t===e))&&(this.clean(e),n.push(e))},syncVolume(e){const n=Math.min(Math.max(0,e/100),1);t.forEach((e=>{e.volume=n}))},syncMute(e){t.forEach((t=>{t.muted=e}))}}}},658:(e,t,n)=>{"use strict";n.d(t,{HB:()=>i,Jx:()=>r,l_:()=>u});const r=4,u=5,i=1},4609:(e,t,n)=>{"use strict";function r(e,t){return Object.assign({},t,{prime(){e.src||e.load()},getPrimedElement:()=>e,clean(){t.clean(e)},recycle(){t.clean(e)}})}n.d(t,{Z:()=>r})},6528:(e,t,n)=>{"use strict";n.d(t,{Z:()=>a});var r=n(1643),u=n(1384);const i=function(){},o=()=>!1,s={name:"default"},a={supports:o,play:i,pause:i,preload:i,load:i,stop:i,volume:i,mute:i,seek:i,resize:i,remove:i,destroy:i,setVisibility:i,setFullscreen(e){return(0,u.CX)(this,e)},getFullscreen:o,supportsFullscreen:o,getContainer:i,setContainer:i,getName:()=>s,getQualityLevels:i,getCurrentQuality:i,setCurrentQuality:i,getAudioTracks:i,getCurrentAudioTrack:i,setCurrentAudioTrack:i,getSeekRange(){return{start:0,end:this.getDuration()}},setPlaybackRate:i,getPlaybackRate:()=>1,getBandwidthEstimate:()=>null,getLiveLatency:()=>null,attachMedia:i,detachMedia:i,init:i,setState(e){this.state=e,this.trigger(r.uc,{newstate:e})},sendMediaType(e){const{type:t,mimeType:n}=e[0],u="aac"===t||"mp3"===t||"mpeg"===t||n&&0===n.indexOf("audio/");this.trigger(r.oZ,{mediaType:u?"audio":"video"})},getDuration:()=>0,trigger:i}},1628:(e,t,n)=>{"use strict";n.d(t,{V:()=>u});var r=n(8348);const u=e=>"hls"===e.type&&r.OS.android?!1!==e.androidhls&&(!r.Browser.firefox&&parseFloat(r.OS.version.version||"0")>=4.4):null},12:(e,t,n)=>{"use strict";n.d(t,{U:()=>r});const r={}},670:(e,t,n)=>{"use strict";n.d(t,{Z:()=>s});var r=n(12),u=n(2963),i=n(6528),o=n(6042);n(328);function s(e){const t=e.getName().name;if(!r.U[t]){if(!(0,o.sE)(u.B,(0,o.wB)({name:t}))){if(!(0,o.mf)(e.supports))throw new Error("Tried to register a provider with an invalid object");u.B.unshift({name:t,supports:e.supports})}0,(0,o.ce)(e.prototype,i.Z),r.U[t]=e}}},6593:(e,t,n)=>{"use strict";n.d(t,{B:()=>a,H:()=>s});var r=n(1628),u=n(7034),i=n(9025);const o={aac:"audio/mp4",mp4:"video/mp4",f4v:"video/mp4",m4v:"video/mp4",mov:"video/mp4",mp3:"audio/mpeg",mpeg:"audio/mpeg",ogv:"video/ogg",ogg:"video/ogg",oga:"video/ogg",vorbis:"video/ogg",webm:"video/webm",f4a:"video/aac",m3u8:"application/vnd.apple.mpegurl",m3u:"application/vnd.apple.mpegurl",hls:"application/vnd.apple.mpegurl"},s=e=>{if(!i.Z||!i.Z.canPlayType)return!1;if(!1===(0,r.V)(e))return!1;const t=e.file,n=e.type;if((0,u.isRtmp)(t,n))return!1;let s=e.mimeType||o[n];if(!s)return!1;const a=e.mediaTypes;return null!=a&&a.length&&(s=[s].concat(a.slice()).join("; ")),Boolean(i.Z.canPlayType(s))},a=[{name:"html5",supports:s}]},1384:(e,t,n)=>{"use strict";n.d(t,{CX:()=>a,IP:()=>d,If:()=>s,Nm:()=>l});var r=n(1643);let u,i,o=!1;const s=()=>o,a=function(e,t){if(t=Boolean(t)){try{const t=e.video.webkitEnterFullscreen||e.video.webkitEnterFullScreen;t&&t.apply(e.video)}catch(e){return!1}return e.getFullscreen()}const n=e.video.webkitExitFullscreen||e.video.webkitExitFullScreen;return n&&n.apply(e.video),t},c=function(e,t,n){o=n,e.trigger(r.h7,{target:t.target,jwstate:n})},l=function(e,t){u=t=>c(e,t,!0),i=t=>c(e,t,!1),t.addEventListener("webkitbeginfullscreen",u),t.addEventListener("webkitendfullscreen",i)},d=e=>{e.removeEventListener("webkitbeginfullscreen",u),e.removeEventListener("webkitendfullscreen",i)}},7642:(e,t,n)=>{"use strict";n.d(t,{b:()=>d,k:()=>f});let r=class e{static normalizeVersion(e,t){return e.trim().replace(/^v/i,"").split(".").map(parseFloat).filter((e=>!Number.isNaN(e))).join(t)}static generateCacheKey(t,n){return`${t}@@${e.normalizeVersion(n,".")}`}static makePromise(){let e,t;const n=new Promise(((n,r)=>{e=n,t=r}));return n.resolve=e,n.reject=t,n}},u=class{get key(){return r.generateCacheKey(this.name,this.version)}constructor(e,t,n){this.name=e,this.version=t,this.promise=n,this.timeoutId=void 0,this.scriptElement=null}};const i="-1.-1.-1";let o=class e{static getServiceLoader(t){const{globalVal:n}=t||{},r=n||window;return r.jwpServices||(r.jwpServices=new e(t)),r.jwpServices}addOverrides(e){if(Array.isArray(e)||"object"!=typeof e||(e=[e]),!Array.isArray(e))throw Error("addOverrides only accepts an array of object or a single object");for(const{name:t,client:n}of e){if(!t||!n)throw Error(`invalid entry was passed to addOverrides. Objects must have a name and a client (url/version). ${JSON.stringify({name:t,client:n})}`);let e=n;/^v?(\d+)(\.\d+)?(\.\d+)?([-+][0-9a-zA-Z-.]*)?$/.test(n)&&(e=this._makeFetchUrl(t,n.replace(/^v/i,""))),this._overrides.set(t,e)}}delOverrides(e){if(Array.isArray(e)||"object"!=typeof e||(e=[e]),!Array.isArray(e))throw Error("delOverrides only accepts an array of object or a single object");for(const{name:t}of e){if(!t)throw Error("invalid entry was passed to delOverrides. Objects must have a name");this._overrides.delete(t)}}async getService(e,t){this._overrides.has(e)&&(t=i);const n=r.generateCacheKey(e,t);if(this._serviceCache.has(n)){return this._serviceCache.get(n)}if(this._loadingEntries.has(e)){const n=this._loadingEntries.get(e);if(n.version===t)return n.promise;if(this._pendingQueue.has(e)){const n=this._pendingQueue.get(e);if(null==n?void 0:n.length){const e=n.find((e=>e.version===t));if(e)return e.promise}}const i=r.makePromise(),o=new u(e,t,i);return this._makePending(o),i}const o=r.makePromise(),s=new u(e,t,o);return this._doLoad(s),o}async registerService(e,t){if(!e||!t)return;const{currentScript:n}=this._global.document,u=await t,o=this._overrides.has(e)?i:u.version,s=r.generateCacheKey(e,o);if(!this._loadingEntries.has(e))return this._registerNonLoadingService(e,t);const a=this._loadingEntries.get(e);if(!a)return;const c=a.promise,l=a.key;if(a.scriptElement!==n)return this._registerNonLoadingService(e,t);this._loadingEntries.delete(e),clearTimeout(a.timeoutId);const d=this._serviceCache.get(s);if(d)return this._serviceCache.set(l,d),this._maybeMovePendingToLoading(e),c.resolve(d);this._serviceCache.set(l,u),l!==s&&this._serviceCache.set(s,c),this._maybeResolveOtherPending(e,t,o),this._maybeMovePendingToLoading(e),c.resolve(t)}async _registerNonLoadingService(e,t){const n=await t,u=this._overrides.has(e)?i:n.version,o=r.generateCacheKey(e,u);this._serviceCache.has(o)||(this._serviceCache.set(o,n),this._maybeResolveOtherPending(e,t,u))}_maybeResolveOtherPending(e,t,n){const r=this._pendingQueue.get(e);if(!r)return;if(!r.length)return void this._pendingQueue.delete(e);const u=r.findIndex((e=>e.version===n));if(-1===u)return;const i=r.splice(u,1)[0];r.length||this._pendingQueue.delete(e),i.promise.resolve(t)}_makePending(e){const{name:t}=e,n=this._pendingQueue.get(t);n?n.push(e):this._pendingQueue.set(t,[e])}_doLoad(e){const{name:t}=e;this._setTimeout(e),this._createScriptElement(e),this._loadingEntries.set(t,e)}_setTimeout(e){const t=new Error("script loading timeout error");e.timeoutId=setTimeout(this._scriptError(e),2e4,t)}_createScriptElement(e){const{name:t,version:n}=e,r=this._global.document.createElement("script");r.type="text/javascript",r.src=this._makeFetchUrl(t,n),r.onerror=this._scriptError(e),r.async=!0,e.scriptElement=r,this._global.document.head.appendChild(r)}_scriptError(e){return t=>{var n;const{name:r,promise:u}=e;clearTimeout(e.timeoutId),e.scriptElement&&(e.scriptElement.onerror=null);const i=(null==e||null==(n=e.scriptElement)?void 0:n.src)?` at ${e.scriptElement.src}`:"",o=(null==t?void 0:t.message)?` with error: ${t.message}`:"";this._loadingEntries.delete(r),this._maybeMovePendingToLoading(r),u.reject(Error(`Failed to load service ${r}${i}${o}`))}}_makeFetchUrl(e,t){const n=this._overrides.get(e);if(n)return n;const u=r.normalizeVersion(t,"/");return`${this._baseUrl}/${e}/v/${u}/index.js`}_maybeMovePendingToLoading(e){const t=this._pendingQueue.get(e);if(!(null==t?void 0:t.length))return;const n=t.shift();n&&this._doLoad(n)}constructor(e){const{baseUrl:t,globalVal:n}=e||{};if(this._baseUrl=t||"https://ssl.p.jwpcdn.com/player/services",this._global=n||window,this._overrides=new Map,this._pendingQueue=new Map,this._loadingEntries=new Map,this._serviceCache=new Map,this._global.location){const e=new URL(this._global.location.href).searchParams.getAll("jwpcslOverride");this.addOverrides(e.reduce(((e,t)=>{const n=t.indexOf(":");if(-1===n)return console.warn("Skipping unsupported jwpcslOverride value",t),e;const r=t.slice(0,n),u=t.slice(n+1);return e.push({name:r,client:u}),e}),[]))}}};var s=n(1237);const a={forcePreroll:!0},c={dynamicAds:(e,t)=>[Object.assign({},t,{experienceName:"player",experience:e,adRules:Object.assign({},a,t.rules)})]};var l=function(e,t){if(null==e)throw new TypeError("Cannot convert undefined or null to object");return Object.prototype.hasOwnProperty.call(Object(e),t)};const d=async(e,t,n,r)=>{const u=o.getServiceLoader(),{name:i,version:s,cfgKey:a}=n;t.set(`services.${i}`,"loading");const l=Object.assign({},r||{});l.client&&(u.addOverrides({name:i,client:l.client}),delete l.client);const d=await u.getService(i,s);if(t.attributes._destroyed)return;const f=((e,t,n)=>c[n]?c[n](e,t):[e,t])(e,l,a),D=await d.register("player",...f);t.attributes._destroyed||t.set(`services.${i}`,D)},f=async function(e,t){const n=t.getConfig(),r=[];for(const u of s.Z){if(!u.name||!u.version||!u.cfgKey)throw Error("SERVICE_DEFINITIONS is invalid. Each service must have name, version, and cfgKey",JSON.stringify(u));const i=u.cfgKey;l(n,i)&&!u.async&&r.push(d(t,e,u,n[i]))}if(n.services)for(const i of n.services){var u;if(!i||!i.name||null==i||null==(u=i.version)||!u.toString().length)throw Error("playerConfig.services must have a defined name and version");r.push(d(t,e,i,i.cfg))}return await Promise.all(r)}},1237:(e,t,n)=>{"use strict";n.d(t,{Z:()=>r});const r=[{name:"discovery-videos",cfgKey:"discoveryVideos",version:"0",async:!0},{name:"dynamic-ad-scheduler",cfgKey:"dynamicAds",version:"0"}]},6875:(e,t,n)=>{"use strict";n.d(t,{Z:()=>r});const r=function(){if("undefined"!=typeof document){if("hidden"in document)return function(){return!document.hidden};if("webkitHidden"in document)return function(){return!document.webkitHidden}}return function(){return!0}}()},6886:(e,t,n)=>{"use strict";n.d(t,{E:()=>s,h:()=>f});var r=n(9888),u=n(7034),i=n(4446);const o=function(){},s=e=>{e.onload=null,e.onprogress=null,e.onreadystatechange=null,e.onerror=null,"abort"in e&&e.abort()},a=(e,t,n,r)=>{e.onerror(t,e.url,e.xhr,new i.rG(t,n,r))},c=(e,t,n)=>{const r=t.documentElement;if(!n.requireValidXML||"parsererror"!==r.nodeName&&!r.getElementsByTagName("parsererror").length)return e.responseXML||(e=Object.assign({},e,{responseXML:t})),n.oncomplete(e);a(n,i.ul,601)},l=e=>function(t){const n=t.currentTarget||e.xhr;if(clearTimeout(e.timeoutId),e.responseType){if("json"===e.responseType)return((e,t)=>{if(!e.response||"string"==typeof e.response&&'"'!==e.responseText.substr(1))try{e=Object.assign({},e,{response:JSON.parse(e.responseText)})}catch(e){return void a(t,i.ul,611,e)}return t.oncomplete(e)})(n,e)}else{let t,o=n.responseXML;if(o)try{t=o.firstChild}catch(e){}if(o&&t)return c(n,o,e);var u;if(e.useDomParser&&n.responseText&&!o)if(o=(0,r.parseXML)(n.responseText),null!=(u=o)&&u.firstChild)return c(n,o,e);if(e.requireValidXML)return void a(e,i.ul,602)}e.oncomplete(n)};let d;const f=(e,t,n,r)=>{var c;let f;e===Object(e)&&(e=(r=e).url);const D=Object.assign({xhr:null,url:e,withCredentials:!1,retryWithoutCredentials:!1,timeout:6e4,timeoutId:-1,oncomplete:t||o,onerror:n||o,mimeType:r&&!r.responseType?"text/xml":"",requireValidXML:!1,responseType:null!=(c=r)&&c.plainText?"text":"",useDomParser:!1,requestFilter:null},r),p=d("Error loading file",D);if("XMLHttpRequest"in window){if(f=D.xhr=D.xhr||new window.XMLHttpRequest,"function"==typeof D.requestFilter){let t;try{t=D.requestFilter({url:e,xhr:f})}catch(e){return p(e,5),f}t&&"open"in t&&"send"in t&&(f=D.xhr=t)}f.onreadystatechange=(e=>function(t){const n=t.currentTarget||e.xhr;if(4===n.readyState){const r=n.status;if(r>=400)return clearTimeout(e.timeoutId),void a(e,i.ul,r<600?r:6);if(r>=200&&r<=299)return clearTimeout(e.timeoutId),l(e)(t);0===r&&(0,u.isFileProtocol)()&&!/^[a-z][a-z0-9+.-]*:/.test(e.url)&&(clearTimeout(e.timeoutId),a(e,i.ul,7))}})(D),f.onerror=p,"overrideMimeType"in f?D.mimeType&&f.overrideMimeType(D.mimeType):D.useDomParser=!0;try{e=e.replace(/#.*$/,""),f.open("GET",e,!0)}catch(e){return p(e,3),f}if(D.responseType)try{f.responseType=D.responseType}catch(e){}D.timeout&&(D.timeoutId=setTimeout((function(){s(f),a(D,i.ud,1)}),D.timeout),f.onabort=function(){clearTimeout(D.timeoutId)});try{D.withCredentials&&"withCredentials"in f&&(f.withCredentials=!0),f.send()}catch(e){p(e,4)}return f}a(D,i.ud,2)};d=(e,t)=>function(e,n){const r=e.currentTarget||t.xhr;if(clearTimeout(t.timeoutId),t.retryWithoutCredentials&&t.xhr.withCredentials){s(r);const e=Object.assign({},t,{xhr:null,withCredentials:!1,retryWithoutCredentials:!1});f(e)}else!n&&r.status>=400&&r.status<600&&(n=r.status),a(t,n?i.ul:i.ud,n||6,e)}},328:(e,t,n)=>{"use strict";n.d(t,{IH:()=>d,S1:()=>f,X$:()=>D,ZP:()=>c,on:()=>l,wj:()=>p});var r=n(8494),u=function(e,t){if(null==e)throw new TypeError("Cannot convert undefined or null to object");return Object.prototype.hasOwnProperty.call(Object(e),t)};const i=r.Z.logger.child("jwplayer/utils/backbone.events"),o=(e,t,n,r)=>{let u=-1;const o=e.length;for(;++u<o;){const o=e[u];if(r)try{o.callback.apply(o.context||n,t)}catch(e){i.debug(`Error in "${r}" event handler:`,e)}else o.callback.apply(o.context||n,t)}},s=/\s+/,a=(e,t,n,r)=>{if(!n)return!0;if("object"==typeof n){for(const i in n)u(n,i)&&e[t].apply(e,[i,n[i]].concat(r));return!1}if(s.test(n)){const u=n.split(s);for(let n=0,i=u.length;n<i;n++)e[t].apply(e,[u[n]].concat(r));return!1}return!0};class c{on(e,t,n){if(!a(this,"on",e,[t,n])||!t)return this;const r=this._events||(this._events={});return(r[e]||(r[e]=[])).push({callback:t,context:n}),this}once(e,t,n){if(!a(this,"once",e,[t,n])||!t)return this;let r=0;const u=this,i=function(){r++||(u.off(e,i),t.apply(this,arguments))};return i._callback=t,this.on(e,i,n)}off(e,t,n){if(!this._events||!a(this,"off",e,[t,n]))return this;if(!e&&!t&&!n)return delete this._events,this;const r=e?[e]:Object.keys(this._events);for(let u=0,i=r.length;u<i;u++){e=r[u];const i=this._events[e];if(i){const r=this._events[e]=[];if(t||n)for(let e=0,u=i.length;e<u;e++){const u=i[e];(t&&t!==u.callback&&t!==u.callback._callback||n&&n!==u.context)&&r.push(u)}r.length||delete this._events[e]}}return this}trigger(e,...t){if(!this._events)return this;if(!a(this,"trigger",e,t))return this;const n=this._events[e],r=this._events.all;return n&&o(n,t,this),r&&o(r,arguments,this),this}triggerSafe(e,...t){if(!this._events)return this;if(!a(this,"trigger",e,t))return this;const n=this._events[e],r=this._events.all;return n&&o(n,t,this,e),r&&o(r,arguments,this,e),this}}const l=c.prototype.on,d=c.prototype.once,f=c.prototype.off,D=c.prototype.trigger,p=c.prototype.triggerSafe;c.on=l,c.once=d,c.off=f,c.trigger=D},2268:(e,t,n)=>{"use strict";n.d(t,{A:()=>d,DF:()=>c,Dt:()=>y,G6:()=>g,NO:()=>A,O7:()=>C,Q6:()=>D,cL:()=>v,dI:()=>E,gn:()=>m,i7:()=>p,id:()=>a,pZ:()=>i,tq:()=>F,un:()=>l,w1:()=>h,xb:()=>o,yS:()=>f,zc:()=>s});const r=e=>null!==navigator.userAgent.match(e),u=()=>"MacIntel"===navigator.platform&&navigator.maxTouchPoints>1,i=()=>r(/firefox\//i),o=()=>r(/iP(hone|od)/i),s=()=>r(/iPad/i)||u(),a=()=>r(/Macintosh/i)&&!u(),c=()=>r(/FBAV/i),l=()=>r(/\sEdge?\/\d+/i),d=()=>r(/msie/i),f=()=>r(/SMART-TV/),D=()=>f()&&!r(/SamsungBrowser/),p=()=>r(/\s(?:(?:Headless)?Chrome|CriOS)\//i)&&!l()&&!r(/UCBrowser/i),h=()=>!r(/\sEdg\/\d+/i)&&(l()||r(/trident\/.+rv:\s*11/i)||d()),g=()=>r(/safari/i)&&!r(/(?:Chrome|CriOS|chromium|android|phantom)/i)&&!f(),m=()=>r(/iP(hone|ad|od)/i)||u(),y=function(){return"boolean"==typeof y.mock_?y.mock_:r(/Android/i)&&!r(/Windows Phone/i)},C=()=>!(r(/chrome\/[123456789]/i)&&!r(/chrome\/18/i)&&!i())&&y();y.mock_=null;const F=()=>m()||y()||r(/Windows Phone/i),v=function(){if("boolean"==typeof v.mock_)return v.mock_;try{return window.self!==window.top}catch(e){return!0}};v.mock_=null;const A=()=>!1,E=()=>0},8381:(e,t,n)=>{"use strict";n.d(t,{$W:()=>s,Mf:()=>c,T2:()=>l,_b:()=>a});var r=n(8518),u=n(2557),i=n(4446);const o=e=>t=>0===t.indexOf(e),s=function(e,t){const n=[];if(!e||!e.timestamps||!e.timestamps.length)return n;const u=e.timestamps.sort(((e,t)=>e.begin-t.begin));return u.forEach(((i,s)=>{const a=((e,t="en")=>{let n=(0,r.G3)();const u=Object.keys(e.title),i=u[0];for(;!e.title[n];){const e=u.find(o(n));if(e){n=e;break}const t=n.lastIndexOf("-");if(t<=0){n=null;break}n=n.slice(0,t)}return n||(u.indexOf(t)>=0?t:i)})(i,e.defaultLanguage),c=i.title[a],l=i.time,d=i.image;let f=t;s+1<u.length&&(f=u[s+1].time);const D={begin:l,end:f,text:c,cueType:"chapters"};d&&(D.image=d),n.push(D)})),n},a=function(e,t){const n=(0,r.G3)(),i=e.reduce((function(e,t){if(!t||!t.cueType||"chapters"===t.cueType){const r=new u.u({time:t.begin,image:t.image});r.addTitle(n,t.text),e.push(r)}return e}),[]);return t?(t.timestamps=i,t):new u.t(n,i)},c=function(e,t){if("number"!=typeof e||e<0||!t||!t.length)return null;let n=null;for(let r=0;r<t.length;r++){const u=t[r];u.time>e||(!n||u.time>n.time)&&(n=u)}return n},l=function(e,t){let n=!0;return e.forEach((e=>{if(!e)return;if(!e.defaultLanguage||!e.timestamps)return void(n=!1);e.timestamps.some((e=>!e.title||null===e.time||void 0===e.time))&&(n=!1)})),t(n?null:(0,i.l9)(new Error,i.aD))}},974:(e,t,n)=>{"use strict";n.d(t,{HY:()=>m,iv:()=>d,oB:()=>l,oI:()=>s,vs:()=>f});var r=n(2957),u=n(9563),i=n.n(u),o=function(e,t){if(null==e)throw new TypeError("Cannot convert undefined or null to object");return Object.prototype.hasOwnProperty.call(Object(e),t)};const s=i().clear,a=e=>{e=e.split("-");for(let t=1;t<e.length;t++)e[t]=e[t].charAt(0).toUpperCase()+e[t].slice(1);return e.join("")},c=(e,t)=>""===t||null==t?"":"string"==typeof t&&isNaN(t)?/png|gif|jpe?g/i.test(t)&&t.indexOf("url")<0?`url(${t})`:t:0===t||"z-index"===e||"opacity"===e?`${t}`:/color/i.test(e)?`#${(0,r.vk)(t.toString(16).replace(/^0x/i,""),6)}`:`${Math.ceil(t)}px`,l=(e,t)=>{if(null==e)return;let n;void 0===e.length&&(e=[e]);const r={};for(n in t)o(t,n)&&(r[n]=c(n,t[n]));for(let t=0;t<e.length;t++){const u=e[t];let i;if(null!=u)for(n in r)o(r,n)&&(i=a(n),u.style[i]!==r[n]&&(u.style[i]=r[n]))}},d=(e,t,n,r)=>{n=n||"all-players";let u="";if("object"==typeof t){const e=document.createElement("div");l(e,t);let n=e.style.cssText;o(t,"content")&&n&&(n=`${n} content: "${t.content}";`),r&&n&&(n=n.replace(/;/g," !important;")),u=`{${n}}`}else"string"==typeof t&&(u=t);""!==u&&"{}"!==u?i().style([[e,e+u]],n):i().clear(n,e)},f=(e,t)=>{l(e,{transform:t})},D={A:{L:"F0F8FF",N:"FAEBD7",Q:{$:2,_:"00FFFF",M:"7FFFD4"},Z:"F0FFFF"},B:{E:"F5F5DC",I:"FFE4C4",L:{A:{C:"000000",N:"FFEBCD"},U:{$:1,_:"0000FF",V:"8A2BE2"}},R:"A52A2A",U:"DEB887"},C:{A:"5F9EA0",H:{A:"7FFF00",O:"D2691E"},O:{$:1,A:"FF7F50",N:{F:"6495ED",S:"FFF8DC"}},R:"DC143C",Y:"00FFFF"},D:{A:{$:2,B:"00008B",C:"008B8B",G:{O:"B8860B",R:{A:"A9A9A9",E:"006400"}},K:"BDB76B",M:"8B008B",O:{L:"556B2F",R:{A:"FF8C00",C:"9932CC"}},R:"8B0000",S:{A:"E9967A",E:"8FBC8B",L:{$:3,B:"483D8B",G:"2F4F4F"}},T:"00CED1",V:"9400D3"},E:{$:2,P:"FF1493",S:"00BFFF"},I:"696969",O:"1E90FF"},F:{I:"B22222",L:"FDF5E6",O:"228B22",U:"FF00FF"},G:{A:"DCDCDC",H:"F8F8FF",O:{$:2,_:"FFD700",E:"DAA520"},R:{A:"808080",E:{$:2,_:"008000",Y:"ADFF2F"}}},H:{$:1,N:"F0FFF0",T:"FF69B4"},I:{N:{$:2,A:"CD5C5C",G:"4B0082"},V:"FFFFF0"},K:"F0E68C",L:{A:{V:{$:5,_:"E6E6FA",B:"FFF0F5"},W:"7CFC00"},E:"FFFACD",I:{G:{$:2,B:"ADD8E6",C:{O:"F08080",Y:"E0FFFF"},G:{O:"FAFAD2",R:{A:"D3D3D3",E:"90EE90"}},P:"FFB6C1",S:{A:"FFA07A",E:"20B2AA",K:"87CEFA",L:"778899",T:"B0C4DE"},Y:"FFFFE0"},M:{$:1,_:"00FF00",G:"32CD32"},N:"FAF0E6"}},M:{A:{G:"FF00FF",R:"800000"},E:{$:4,A:"66CDAA",B:"0000CD",O:"BA55D3",P:"9370DB",S:{E:"3CB371",L:"7B68EE",P:"00FA9A"},T:"48D1CC",V:"C71585"},I:{D:"191970",N:"F5FFFA",S:"FFE4E1"},O:"FFE4B5"},N:{$:2,A:"FFDEAD",Y:"00008B"},O:{L:{D:"FDF5E6",I:{$:2,_:"808000",D:"6B8E23"}},R:{A:{$:3,_:"FFA500",R:"FF4500"},C:"DA70D6"}},P:{A:{L:{$:1,G:{O:"EEE8AA",R:"98FB98"},T:"AFEEEE",V:"DB7093"},P:"FFEFD5"},E:{A:"FFDAB9",R:"CD853F"},I:"FFC0CB",L:"DDA0DD",O:"B0E0E6",U:"800080"},R:{E:{B:"663399",D:"FF0000"},O:{S:"BC8F8F",Y:"4169E1"}},S:{A:{D:"8B4513",L:"FA8072",N:"F4A460"},E:{$:1,G:"2E8B57",S:"FFF5EE"},I:{E:"A0522D",L:"C0C0C0"},K:"87CEEB",L:{$:3,B:"6A5ACD",G:"708090"},N:"FFFAFA",P:"00FF7F",T:"4682B4"},T:{A:"D2B48C",E:"008080",H:"D8BFD8",O:"FF6347",U:"40E0D0"},V:"EE82EE",W:{$:1,E:"F5DEB3",I:{$:2,_:"FFFFFF",S:"F5F5F5"}},Y:{$:5,_:"FFFF00",G:"9ACD32"}},p=e=>parseInt(e,16),h=(e,t)=>`${e}(${t[0]}, ${t[1]}, ${t[2]}, ${t[3]})`,g=[{name:"extended hash-hex",test:/^#?[0-9a-f]{8}$/i,extract:/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i,map:p,alpha:!0},{name:"standard hash-hex",test:/^#?[0-9a-f]{6}$/i,extract:/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i,map:p},{name:"short hash-hex",test:/^#?[0-9a-f]{3}$/i,extract:/^#?([0-9a-f])([0-9a-f])([0-9a-f])/i,map:e=>17*parseInt(e,16)}],m=(e,t,n=!1)=>{var r;e="string"==typeof e?e.trim():"#000000";let u="rgba",i=["0","0","0","1"];const o=(t="number"==typeof t?t:100)/100;if(/^\w+\(/i.test(e))return u=/^(\w+)\(/i.exec(e)[1],i=/^\w+\(([^),]+),\s*([^,)]+),\s*([^,)]+),?\s*([^),]*)\)/i.exec(e).slice(1),3===u.length&&(u+="a"),n&&i[3].length?i[3]*=o:i[3]=o,h(u,i);e=null!=(r=(e=>{let t=0,n=D;for(;n&&t<e.length;){if(n=n[e[t]],t++,!n)return null;if("string"==typeof n)return n;if(n.$&&(t+=n.$),t===e.length&&n._)return n._}return null})(e=e.toUpperCase().replace("GREY","GRAY")))?r:e;for(let t=0;t<g.length;t++){const r=g[t];if(r.test.test(e))return i=r.extract.exec(e).slice(1).map(r.map),n&&r.alpha?i[3]=i[3]/255*o:i[3]=o,h(u,i)}return h(u,i)}},5004:(e,t,n)=>{"use strict";n.d(t,{z:()=>r});const r=Date.now||function(){return(new Date).getTime()}},2799:(e,t,n)=>{"use strict";n.d(t,{A8:()=>B,AH:()=>j,EU:()=>D,FK:()=>h,IV:()=>F,L_:()=>v,P$:()=>E,SH:()=>k,UM:()=>O,Ww:()=>x,az:()=>f,bJ:()=>d,cS:()=>w,cn:()=>C,gB:()=>l,i3:()=>P,kq:()=>b,nG:()=>S,nh:()=>p,oH:()=>a,og:()=>A,pv:()=>s,s1:()=>y});var r=n(2957),u=n(6042),i=n(8348),o=n(8494);const s=(e,t)=>e.classList.contains(t),a=e=>{const t=e.querySelectorAll("script,object,iframe,meta");for(let e=t.length;e--;){const n=t[e];n.parentNode.removeChild(n)}return e},c=/^((((https?):\/\/)|(mailto:))(%[0-9A-Fa-f]{2}|[-()_.!~*';/?:@&=+$,A-Za-z0-9])+)([).!';/?:,][[:blank:|:blank:]])?$/,l=e=>{const t=e.attributes;for(let n=t.length;n--;){const r=t[n].name,u=t[n].value;/^\s*(javascript(:|&colon;))/.test(u)&&(e.removeAttribute(r),o.Z.logger.warn("jwplayer/utils/dom: Invalid or unsafe URL")),/^on/.test(r)&&e.removeAttribute(r)}return e},d=e=>{const t=(e=>{const t=document.createElement("div");return t.innerHTML=null==e||null==e.trim?void 0:e.trim(),t})(e);a(t);const n=t.querySelectorAll("*");for(let e=n.length;e--;){const t=n[e];l(t)}return t},f=e=>d(e).firstChild,D=e=>{for(;e.firstChild;)e.removeChild(e.firstChild)},p=(e,t)=>{D(e),((e,t)=>{if(!t)return;const n=d(t).childNodes;for(let t=0;t<n.length;t++)e.appendChild(n[t].cloneNode(!0))})(e,t)},h=e=>e+(e.toString().indexOf("%")>0?"":"px"),g=e=>(0,u.HD)(e.className)?e.className.split(" "):[],m=(e,t)=>{t=(0,r.fy)(t),e.className!==t&&(e.className=t)},y=e=>e.classList?e.classList:g(e),C=(e,t)=>{const n=g(e);(Array.isArray(t)?t:t.split(" ")).forEach((function(e){(0,u.r3)(n,e)||n.push(e)})),m(e,n.join(" "))},F=(e,t)=>{const n=g(e),r=Array.isArray(t)?t:t.split(" ");m(e,(0,u.e5)(n,r).join(" "))},v=(e,t,n)=>{let r=e.className||"";t.test(r)?r=r.replace(t,n):n&&(r+=` ${n}`),m(e,r)},A=(e,t,n)=>{const r=s(e,t);(n=(0,u.jn)(n)?n:!r)!==r&&(n?C(e,t):F(e,t))},E=(e,t,n)=>{e.setAttribute(t,n)},b=e=>{const t=document.createElement("link");t.rel="stylesheet",t.href=e,document.getElementsByTagName("head")[0].appendChild(t)},w=e=>{e&&D(e)},B=e=>{const t={left:0,right:0,width:0,height:0,top:0,bottom:0};if(!e||!document.body.contains(e))return t;const n=e.getBoundingClientRect(),r=window.pageYOffset,u=window.pageXOffset;return n.width||n.height||n.left||n.top?(t.left=n.left+u,t.right=n.right+u,t.top=n.top+r,t.bottom=n.bottom+r,t.width=n.right-n.left,t.height=n.bottom-n.top,t):t},k=(e,t)=>{e.insertBefore(t,e.firstChild)},j=e=>e.nextElementSibling,P=e=>e.previousElementSibling,S=(e,t,n={},r=document)=>{if(!c.test(e))return;let u=r.createElement("a");u.href=e,u.target=t,u=l(Object.assign(u,n)),i.Browser.firefox?u.dispatchEvent(new MouseEvent("click",{bubbles:!0,cancelable:!0,view:window})):u.click()},O=()=>{const e=window.screen.orientation;return!!e&&("landscape-primary"===e.type||"landscape-secondary"===e.type)||90===window.orientation||-90===window.orientation},x=e=>(e=>{const t=document.createElement("textarea");return t.innerHTML=e,t.value})(e).replace(/&|<|>|"|''/gm,(function(e){return`&#${e.charCodeAt(0)};`})).replace(/&#60;(\/?)(b|strong|i|em|p|br|ul|ol|li|h.)&#62;/gim,"<$1$2>")},8494:(e,t,n)=>{"use strict";n.d(t,{Z:()=>v});var r=n(1569),u=n(7034),i=n(9888),o=n(2957),s=n(7411),a=n(4742);const c=function(e,t){this.name=e,this.message=t.message||t.toString(),this.error=t};var l=n(6042),d=n(2268),f=n(2799),D=n(974),p=n(6886),h=n(1261);const g="function"==typeof console.log?console.log.bind(console):()=>{};var m=n(6234),y=n(8762),C=function(e,t){if(null==e)throw new TypeError("Cannot convert undefined or null to object");return Object.prototype.hasOwnProperty.call(Object(e),t)};const F=new y.Z("helpers");const v=Object.assign({},i,u,r,{logger:F,addClass:f.cn,hasClass:f.pv,removeClass:f.IV,replaceClass:f.L_,toggleClass:f.og,classList:f.s1,styleDimension:f.FK,createElement:f.az,emptyElement:f.EU,addStyleSheet:f.kq,bounds:f.A8,openLink:f.nG,replaceInnerHtml:f.nh,css:D.iv,clearCss:D.oI,style:D.oB,transform:D.vs,getRgba:D.HY,ajax:p.h,crossdomain:e=>{const t=window.URL;try{const n=new t(e,location.origin);return`${location.protocol}//${location.host}`!=`${n.protocol}//${n.host}`}catch(e){F.debug(e)}return!0},tryCatch:function(e,t,n=[]){if(a.Z.debug)return e.apply(t||this,n);try{return e.apply(t||this,n)}catch(t){return new c(e.name,t)}},Error:c,Timer:s.Z,log:g,genId:m.B,between:h.v,foreach:function(e,t){for(const n in e)C(e,n)&&t(n,e[n])},flashVersion:d.dI,isIframe:d.cL,indexOf:l.cq,trim:o.fy,pad:o.vk,extension:o.AO,hms:o.WZ,seconds:o.m9,prefix:o.O4,suffix:o.uA,noop:()=>{}})},7543:(e,t,n)=>{"use strict";n.d(t,{C:()=>r});const r=e=>!!(e=e||window.event)&&(Boolean(e)&&/^(?:mouse|pointer|touch|gesture|click|key)/.test(e.type))},8762:(e,t,n)=>{"use strict";n.d(t,{Z:()=>s});var r=n(1142);const u={debug:0,info:100,warn:200,error:400},i=e=>{var t;switch(typeof e){case"object":return(e=>{if(null===e)return"null";let t="";try{t+=r.stringify(e,null,"  ")}catch(e){t+="{error stringifying value}"}return t})(e);case"undefined":return"undefined";default:return null!=(t=null==e.toString?void 0:e.toString())?t:"{error stringifying value}"}};class o{constructor(e,t=u){this._namespace=e,this._levels=t}child(e){return new o(`${this._namespace}/${e}`,this._levels)}_log(e,t,...n){try{e>=o.LOG_LEVEL&&console[t](`[${this._namespace}]:`,...n),o.LOG_HISTORY.length>=o.MAX_LOG_HISTORY&&o.LOG_HISTORY.shift(),o.LOG_HISTORY.push([new Date,t.toUpperCase(),this._namespace,n.map(i).join("\n")])}catch(e){console.error(e)}}trace(...e){this._log(this._levels.debug,"trace",...e)}debug(...e){this._log(this._levels.debug,"debug",...e)}log(...e){this._log(this._levels.info,"log",...e)}info(...e){this._log(this._levels.info,"info",...e)}warn(...e){this._log(this._levels.warn,"warn",...e)}error(...e){this._log(this._levels.error,"error",...e)}get history(){return[...o.LOG_HISTORY]}}o.LOG_LEVEL=400,o.MAX_LOG_HISTORY=200,o.LOG_HISTORY=[];const s=o},8518:(e,t,n)=>{"use strict";n.d(t,{Cq:()=>m,Dq:()=>B,G3:()=>C,Mh:()=>j,Pm:()=>b,dl:()=>w,id:()=>g,q2:()=>A,t6:()=>v,tK:()=>h});var r=n(6042),u=n(2268),i=n(6886),o=n(7034),s=n(696),a=n(8494);const{logger:c}=a.Z,l={},d={aa:"Afar",ab:"Abkhazian",ae:"Avestan",af:"Afrikaans",ak:"Akan",am:"Amharic",ar:"Arabic",an:"Aragonese",as:"Assamese",av:"Avaric",ay:"Aymara",az:"Azerbaijani",ba:"Bashkir",be:"Belarusian",bg:"Bulgarian",bh:"Bihari languages",bi:"Bislama",bm:"Bambara",bn:"Bengali",bo:"Tibetan",br:"Breton",bs:"Bosnian",ca:"Catalan",ce:"Chechen",ch:"Chamorro",co:"Corsican",cr:"Cree",cs:"Czech",cu:"Church Slavic",cv:"Chuvash",cy:"Welsh",da:"Danish",de:"German",dv:"Divehi",dz:"Dzongkha",ee:"Ewe",el:"Greek",en:"English",eo:"Esperanto",es:"Spanish",et:"Estonian",eu:"Basque",fa:"Persian",ff:"Fulah",fi:"Finnish",fj:"Fijian",fo:"Faroese",fr:"French",fy:"Western Frisian",ga:"Irish",gd:"Gaelic",gl:"Galician",gn:"Guarani",gu:"Gujarati",gv:"Manx",ha:"Hausa",he:"Hebrew",hi:"Hindi",ho:"Hiri Motu",hr:"Croatian",ht:"Haitian",hu:"Hungarian",hy:"Armenian",hz:"Herero",ia:"Interlingua",id:"Indonesian",ie:"Interlingue",ig:"Igbo",ii:"Sichuan Yi",ik:"Inupiaq",io:"Ido",is:"Icelandic",it:"Italian",iu:"Inuktitut",ja:"Japanese",jv:"Javanese",ka:"Georgian",kg:"Kongo",ki:"Kikuyu",kj:"Kuanyama",kk:"Kazakh",kl:"Kalaallisut",km:"Central Khmer",kn:"Kannada",ko:"Korean",kr:"Kanuri",ks:"Kashmiri",ku:"Kurdish",kv:"Komi",kw:"Cornish",ky:"Kirghiz",la:"Latin",lb:"Luxembourgish",lg:"Ganda",li:"Limburgan",lo:"Lao",ln:"Lingala",lt:"Lithuanian",lu:"Luba-Katanga",lv:"Latvian",mg:"Malagasy",mh:"Marshallese",mi:"Maori",mk:"Macedonian",ml:"Malayalam",mn:"Mongolian",mr:"Marathi",ms:"Malay",mt:"Maltese",my:"Burmese",na:"Nauru",nb:"Bokmål",nd:"Ndebele",ne:"Nepali",ng:"Ndonga",nl:"Dutch",nn:"Norwegian Nynorsk",no:"Norwegian",nr:"Ndebele",nv:"Navajo",ny:"Chichewa",oc:"Occitan",oj:"Ojibwa",om:"Oromo",or:"Oriya",os:"Ossetian",pa:"Panjabi",pi:"Pali",pl:"Polish",pt:"Portuguese",ps:"Pushto",qu:"Quechua",rm:"Romansh",rn:"Rundi",ro:"Romanian",ru:"Russian",rw:"Kinyarwanda",sa:"Sanskrit",sc:"Sardinian",sd:"Sindhi",se:"Northern Sami",sg:"Sango",si:"Sinhala",sk:"Slovak",sl:"Slovenian",sm:"Samoan",sn:"Shona",so:"Somali",sq:"Albanian",sr:"Serbian",ss:"Swati",st:"Sotho",su:"Sundanese",sw:"Swahili",sv:"Swedish",ta:"Tamil",te:"Telugu",tg:"Tajik",th:"Thai",ti:"Tigrinya",tk:"Turkmen",tl:"Tagalog",tn:"Tswana",to:"Tonga",tr:"Turkish",ts:"Tsonga",tt:"Tatar",tw:"Twi",ty:"Tahitian",ug:"Uighur",uk:"Ukrainian",ur:"Urdu",uz:"Uzbek",ve:"Venda",vi:"Vietnamese",vo:"Volapük",wa:"Walloon",wo:"Wolof",xh:"Xhosa",yi:"Yiddish",yo:"Yoruba",za:"Zhuang",zh:"Chinese","zh-tw":"Traditional Chinese",zu:"Zulu"},f=(0,r.U_)(d),D=e=>e.toLowerCase().replace("-","_"),p=e=>{if(e=e.toLowerCase(),d[e])return e;const t=D(e).lastIndexOf("_");if(-1===t)return e;const n=e.substring(0,t);return p(n)},h=e=>e?Object.keys(e).reduce(((t,n)=>(t[D(n)]=e[n],t)),{}):{},g=e=>{if(e)return 3===e.length?e:d[p(e)]||e},m=e=>f[e]||"",y=e=>{const t=e.querySelector("html");return t?t.getAttribute("lang"):null},C=function(){if("string"==typeof C.mock_)return C.mock_;let e=y(document);if(!e&&(0,u.cL)())try{e=y(window.top.document)}catch(e){c.child("jwplayer/utils/language").debug(e)}return e||navigator.language||"en"};C.mock_=null;const F=["ar","da","de","el","es","fi","fr","he","id","it","ja","ko","nb","nl","nn","no","oc","pt","ro","ru","sl","sv","th","tr","vi","zh-tw","zh"],v=e=>8207===e.charCodeAt(0)||/^[\u0591-\u07FF\uFB1D-\uFDFD\uFE70-\uFEFC]/.test(e),A=function(e){return"boolean"==typeof A.mock_?A.mock_:F.indexOf(p(e))>=0};A.mock_=null;const E=(e,t,n)=>{const r=e[n]||t[n];r&&(e[n]=r)},b=(e,t,n)=>Object.assign({},(e=>{const{advertising:t,related:n,sharing:r,abouttext:u}=e,i=Object.assign({},e.localization);t&&(i.advertising=i.advertising||{},E(i.advertising,t,"admessage"),E(i.advertising,t,"cuetext"),E(i.advertising,t,"loadingAd"),E(i.advertising,t,"podmessage"),E(i.advertising,t,"skipmessage"),E(i.advertising,t,"skiptext")),"string"==typeof i.related?i.related={heading:i.related}:i.related=i.related||{},n&&E(i.related,n,"autoplaymessage"),r&&(i.sharing=i.sharing||{},E(i.sharing,r,"heading"),E(i.sharing,r,"copied")),u&&E(i,e,"abouttext");const o=i.close||i.nextUpClose;return o&&(i.close=o),i})(e),t[p(n)],t[D(n)]),w=function(e){return"boolean"==typeof w.mock_?w.mock_:(0,o.isDeepKeyCompliant)(s.Z,e,((e,t)=>"string"==typeof t[e]))};w.mock_=null;const B=function(e,t){if("function"==typeof B.mock_)return B.mock_();let n=l[t];if(!n){const u=`${e}translations/${r=p(t),/^n[bn]$/.test(r)?"no":r}.json`;l[t]=n=new Promise(((e,n)=>{(0,i.h)({url:u,oncomplete:e,onerror:(e,r,u,i)=>{l[t]=null,n(i)},responseType:"json"})}))}var r;return n};B.mock_=null;const k=(e,t,n,r)=>{e[t]=Object.assign({},s.Z[t],n[t],r[t])},j=(e,t)=>{const n=Object.assign({},s.Z,e,t);return k(n,"errors",e,t),k(n,"related",e,t),k(n,"sharing",e,t),k(n,"advertising",e,t),k(n,"shortcuts",e,t),k(n,"captionsStyles",e,t),n}},1261:(e,t,n)=>{"use strict";n.d(t,{v:()=>r});const r=function(e,t,n){return Math.max(Math.min(e,n),t)}},9888:(e,t,n)=>{"use strict";n.r(t),n.d(t,{getAbsolutePath:()=>o,isAbsolutePath:()=>i,parseDimension:()=>c,parseXML:()=>s,serialize:()=>a,timeFormat:()=>l,timeFormatAria:()=>d});var r=n(6042),u=n(5950);const i=e=>/^(?:(?:https?|file):)?\/\//.test(e),o=(e,t)=>(0,u.kd)(e,t),s=e=>{let t=null;try{t=(new window.DOMParser).parseFromString(e,"text/xml"),t.querySelector("parsererror")&&(t=null)}catch(e){}return t},a=e=>{if(void 0===e)return null;if("string"==typeof e&&e.length<6){const t=e.toLowerCase();if("true"===t)return!0;if("false"===t)return!1;if(!(0,r.i2)(Number(e))&&!(0,r.i2)(parseFloat(e)))return Number(e)}return e},c=e=>(0,r.qh)(e)?e:""===e?0:e.lastIndexOf("%")>-1?e:parseInt(e.replace("px",""),10),l=(e,t)=>{if((0,r.i2)(e)&&(e=parseInt(e.toString(),10)),(0,r.i2)(e)||!isFinite(e)||e<=0&&!t)return"00:00";const n=e<0?"-":"";e=Math.abs(e);const u=Math.floor(e/3600),i=Math.floor((e-3600*u)/60),o=Math.floor(e%60);return`${n+(u?`${u}:`:"")+(i<10?"0":"")+i}:${o<10?"0":""}${o}`},d=e=>{if((0,r.i2)(e)&&(e=parseInt(e.toString(),10)),(0,r.i2)(e)||!isFinite(e)||e<=0)return"0 seconds";const t=Math.floor(e/3600),n=Math.floor((e-3600*t)/60),u=Math.floor(e%60);return(t?t+(t>=1?` hour${t>1?"s":""}, `:""):"")+(n?n+(n>=1?` minute${n>1?"s":""}, `:""):"")+u+(u>=1?" second"+(u>1?"s":""):"")}},1569:(e,t,n)=>{"use strict";n.r(t),n.d(t,{getScriptPath:()=>i,loadFrom:()=>a,repo:()=>o,versionCheck:()=>s});var r=n(6601),u=n(7034);const i=function(e){{const t=document.getElementsByTagName("script");for(let n=0;n<t.length;n++){const r=t[n].src;if(r){const t=r.lastIndexOf(`/${e}`);if(t>=0)return r.substr(0,t+1)}}}return""},o=function(){const e="//ssl.p.jwpcdn.com/player/v/8.38.8";return`${e&&(0,u.isFileProtocol)()?"https:":""}${e}`},s=function(e){const t=`0${e}`.split(/\W/),n=r.i.split(/\W/),u=parseFloat(t[0]),i=parseFloat(n[0]);return!(u>i)&&!(u===i&&parseFloat(`0${t[1]}`)>parseFloat(n[1]))},a=function(){return o()}},6234:(e,t,n)=>{"use strict";n.d(t,{B:()=>o,F:()=>u});var r=n(8494);const u=12,i=()=>{try{const e=window.crypto||window.msCrypto;if(null!=e&&e.getRandomValues)return e.getRandomValues(new Uint32Array(1))[0].toString(36)}catch(e){r.Z.logger.debug("jwplayer/utils/random-id-generator: ",e)}return Math.random().toString(36).slice(2,9)},o=e=>{let t="";for(;t.length<e;)t+=i();return t.slice(0,e)}},1776:(e,t,n)=>{"use strict";n.d(t,{U:()=>r,W:()=>u});const r=window.requestAnimationFrame||(e=>setTimeout(e,17)),u=window.cancelAnimationFrame||clearTimeout},676:(e,t,n)=>{"use strict";n.d(t,{ZP:()=>c});var r=n(328),u=n(1643);const i={},o=e=>{const t=document.createElement("link");return t.type="text/css",t.rel="stylesheet",t.href=e,t},s=(e,t)=>{const n=document.createElement("script");return n.type="text/javascript",n.charset="utf-8",n.async=!0,n.timeout=t||45e3,n.src=e,n},a=function(e,t,n){const r=this;let a=0;const c=e=>{a=2,r.trigger(u.pn,e).off()},l=e=>{a=3,r.trigger(u.xQ,e).off()};this.getStatus=function(){return a},this.load=function(){let r=i[e];return 0!==a||(r&&r.then(l).catch(c),a=1,r=new Promise(((r,u)=>{const i=(t?o:s)(e,n);let a;const d=function(){i.onerror=i.onload=null,clearTimeout(a)},f=function(e){d(),c(e),u(e)};a=setTimeout((()=>{f(new Error(`Network timeout ${e}`))}),45e3),i.onerror=function(){f(new Error(`Failed to load ${e}`))},i.onload=function(e){d(),l(e),r(e)};const D=document.getElementsByTagName("head")[0]||document.documentElement;D.insertBefore(i,D.firstChild)})),i[e]=r),r}};Object.assign(a.prototype,r.ZP);const c=a},2957:(e,t,n)=>{"use strict";n.d(t,{AO:()=>a,Dc:()=>s,O4:()=>f,U5:()=>d,WZ:()=>c,fy:()=>i,m9:()=>l,uA:()=>D,vk:()=>o,zz:()=>p});var r=n(6042);const u=window.parseFloat,i=e=>e.replace(/^\s+|\s+$/g,""),o=(e,t,n)=>{for(e=`${e}`,n=n||"0";e.length<t;)e=n+e;return e},s=(e,t)=>{const n=e.attributes;for(let e=0;e<n.length;e++)if(n[e].name&&n[e].name.toLowerCase()===t.toLowerCase())return n[e].value.toString();return""},a=e=>{if(!e||"rtmp"===e.substr(0,4))return"";const t=/[(,]format=(m3u8|mpd)-/i.exec(e);if(t)return t[1];const n=e.replace(/^.+?\.(\w+)(?:[;].*)?(?:[?#].*)?$/,"$1");return n!==e?n.toLowerCase():(e=e.split("?")[0].split("#")[0]).lastIndexOf(".")>-1?e.substr(e.lastIndexOf(".")+1,e.length).toLowerCase():""},c=e=>{const t=(e/60|0)%60,n=e%60;return`${o((e/3600|0).toString(),2)}:${o(t.toString(),2)}:${o(n.toFixed(3),6)}`},l=(e,t)=>{if(!e)return 0;if((0,r.qh)(e))return e;const n=e.replace(",","."),i=n.slice(-1),o=n.split(":"),s=o.length;let a=0;if("s"===i)a=u(n);else if("m"===i)a=60*u(n);else if("h"===i)a=3600*u(n);else if(s>1){let e=s-1;4===s&&(t&&(a=u(o[e])/t),e-=1),a+=u(o[e]),a+=60*u(o[e-1]),s>=3&&(a+=3600*u(o[e-2]))}else a=u(n);return(0,r.qh)(a)?a:0},d=(e,t,n)=>{if((0,r.HD)(e)&&"%"===e.slice(-1)){const n=u(e);return t&&(0,r.qh)(t)&&(0,r.qh)(n)?t*n/100:null}return l(e,n)},f=(e,t)=>e.map((e=>t+e)),D=(e,t)=>e.map((e=>e+t)),p=e=>Boolean(e)&&(0,r.HD)(e)&&"%"===e.slice(-1)},5882:(e,t,n)=>{"use strict";n.d(t,{GU:()=>v,ZP:()=>T,dO:()=>w});var r=n(8348),u=n(1643),i=n(328),o=n(5004),s=n(2799);const a="ontouchstart"in window,c="PointerEvent"in window&&!r.OS.android,l=!(c||a&&r.OS.mobile),d="window",f="init",D="select",p="keydown",{passiveEvents:h}=r.Features,g=!!h&&{passive:!0};let m,y;const C=(e,t,n)=>{const{el:r}=e,u=((e,t,n)=>{const{target:r,touches:u,changedTouches:i}=t;let o,{pointerType:s}=t;u||i?(o=null!=u&&u.length?u[0]:i[0],s=s||"touch"):(o=t,s=s||"mouse");const{pageX:a,pageY:c}=o;return{type:e,pointerType:s,pageX:a,pageY:c,sourceEvent:t,currentTarget:n,target:r}})(t,n,r);e.trigger(t,u)},F=(e,t,n)=>{const{el:r}=e,{target:u}=n;e.trigger(t,{type:t,sourceEvent:n,currentTarget:r,target:u})},v=e=>{const t=e.ownerDocument||e;return t.defaultView||t.parentWindow||window},A=(e,t,n,r,u=g)=>{let i=e.handlers[t],o=e.options[t];if(i||(i=e.handlers[t]={},o=e.options[t]={}),i[n])throw new Error(`${t} ${n} already registered`);i[n]=r,o[n]=u;const{el:s}=e,a=t===d?v(s):s;a&&a.addEventListener(n,r,u)},E=e=>{const{el:t}=e;null!==e.pointerId&&(t.releasePointerCapture(e.pointerId),e.pointerId=null)},b=(e,t)=>{const{el:n,handlers:r,options:u}=e,i=t===d?v(n):n,o=r[t],s=u[t];o&&(Object.keys(o).forEach((e=>{const t=s[e];"boolean"==typeof t?i.removeEventListener(e,o[e],t):i.removeEventListener(e,o[e])})),r[t]=null,u[t]=null)},w=e=>!(!Boolean(e.ctrlKey)||"click"!==e.type)||("which"in e?3===e.which:"button"in e&&2===e.button),B=(e,t)=>{if(y||(y=new T(document).on("interaction")),e.handlers[f]||e.handlers[D])return;const{el:n}=e;A(e,t,"blur",(()=>{(0,s.IV)(n,"jw-tab-focus"),e.clicking=!1})),A(e,t,"focus",(()=>{y.event&&y.event.type===p&&(0,s.cn)(n,"jw-tab-focus")}))},k=(e,t,n,r)=>{c?A(e,t,"pointerdown",n,r):(l&&A(e,t,"mousedown",n,r),A(e,t,"touchstart",n,r))},j=e=>{if(e.handlers[D])return;const{el:t}=e;B(e,D),k(e,D,(n=>{const{target:r}=n;w(n)||Boolean(e.directSelect)&&r!==t||(n.isPrimary&&"BUTTON"===r.tagName&&r.focus(),e.lastStart=(0,o.z)(),e.clicking=!0)})),A(e,D,"click",(n=>{w(n)||Boolean(e.directSelect)&&n.target!==t||((0,o.z)()-e.lastStart>500&&!0===e.clicking||(((e,t)=>{e.enableDoubleClick&&((0,o.z)()-e.lastClick<300?(C(e,u.P,t),e.lastClick=0):e.lastClick=(0,o.z)())})(e,n),C(e,u.ot,n)),e.clicking=!1)}))},P=e=>0===e.type.indexOf("touch")?(e.originalEvent||e).changedTouches[0]:e,S=e=>{if(e.handlers[f])return;const{el:t,passive:n}=e,r=!!h&&{passive:n},i=t=>{if(e.dragged)C(e,u.Wp,t);else{const{pageX:n,pageY:r}=P(t),i=n-e.startX,o=r-e.startY;i*i+o*o>36&&(C(e,u.nv,t),e.dragged=!0,C(e,u.Wp,t))}var r;n||"touchmove"!==t.type||(r=t).preventDefault&&r.preventDefault()},o=t=>{clearTimeout(m),e.el&&(E(e),b(e,d),e.dragged&&(e.dragged=!1,C(e,u.Sv,t)))};B(e,f),k(e,f,(u=>{if((0,s.IV)(t,"jw-tab-focus"),w(u))return;const{target:a,type:c}=u;if(e.directSelect&&a!==t)return;const{pageX:l,pageY:f}=P(u);if(e.dragged=!1,e.startX=l,e.startY=f,b(e,d),"pointerdown"===c&&u.isPrimary){if(!n){const{pointerId:n}=u;e.pointerId=n,t.setPointerCapture(n)}A(e,d,"pointermove",i,r),A(e,d,"pointercancel",o),A(e,d,"pointerup",o)}else"mousedown"===c?(A(e,d,"mousemove",i,r),A(e,d,"mouseup",o)):"touchstart"===c&&(A(e,d,"touchmove",i,r),A(e,d,"touchcancel",o),A(e,d,"touchend",o))}),r)},O={drag(e){S(e)},dragStart(e){S(e)},dragEnd(e){S(e)},click(e){j(e)},doubleClick(e){e.enableDoubleClick=!0,j(e)},longPress(e){const t="longPress";if(r.OS.iOS){const n=()=>{clearTimeout(m)};A(e,t,"touchstart",(r=>{n(),m=setTimeout((()=>{C(e,t,r)}),500)})),A(e,t,"touchmove",n),A(e,t,"touchcancel",n),A(e,t,"touchend",n)}else e.el.oncontextmenu=n=>(C(e,t,n),!1)},focus(e){const t="focus";A(e,t,t,(n=>{F(e,t,n)}))},blur(e){const t="blur";A(e,t,t,(n=>{F(e,t,n)}))},over(e){(c||l)&&A(e,u.B1,c?"pointerover":"mouseover",(t=>{"touch"!==t.pointerType&&C(e,u.B1,t)}))},out(e){if(c){const{el:t}=e;A(e,u.U3,"pointerout",(n=>{if("touch"!==n.pointerType&&"clientX"in n){const r=document.elementFromPoint(n.clientX,n.clientY);t.contains(r)||C(e,u.U3,n)}}))}else l&&A(e,u.U3,"mouseout",(t=>{C(e,u.U3,t)}))},move(e){(c||l)&&A(e,u.tP,c?"pointermove":"mousemove",(t=>{"touch"!==t.pointerType&&C(e,u.tP,t)}))},enter(e){A(e,u.K5,p,(t=>{"Enter"!==t.key&&13!==t.keyCode||(t.stopPropagation(),F(e,u.K5,t))}))},keydown(e){A(e,p,p,(t=>{F(e,p,t)}),!1)},gesture(e){const t="gesture",n=n=>C(e,t,n);A(e,t,"click",n),A(e,t,p,n)},interaction(e){const t="interaction",n=t=>{e.event=t};A(e,t,"mousedown",n,!0),A(e,t,p,n,!0)},tap(){},doubleTap(){}},x=/\s+/,_=e=>e&&!(x.test(e)||"object"==typeof e);class T extends i.ZP{constructor(e,t){super();const n=!(t=t||{}).preventScrolling;this.directSelect=Boolean(t.directSelect),this.dragged=!1,this.enableDoubleClick=!1,this.el=e,this.handlers={},this.options={},this.lastClick=0,this.lastStart=0,this.passive=n,this.pointerId=null,this.startX=0,this.startY=0,this.event=null,this.clicking=!1}on(e,t,n){return _(e)&&(this.handlers[e]||O[e](this)),super.on(e,t,n)}off(e,t,n){if(_(e))b(this,e);else if(!e){const{handlers:e}=this;Object.keys(e).forEach((e=>{b(this,e)}))}return super.off(e,t,n)}destroy(){this.el&&(this.off(),c&&E(this),this.el=null)}}},6042:(e,t,n)=>{"use strict";n.d(t,{Cb:()=>ue,HD:()=>T,Kn:()=>w,P2:()=>Ae,S6:()=>k,UI:()=>Z,U_:()=>Ee,Yj:()=>V,ZP:()=>Pe,_e:()=>he,a9:()=>ke,ar:()=>pe,ce:()=>be,cq:()=>le,dp:()=>Y,e1:()=>ce,e5:()=>ge,ei:()=>Be,hX:()=>W,hj:()=>_,i2:()=>N,jn:()=>ne,l7:()=>we,mf:()=>x,o8:()=>re,qh:()=>je,r3:()=>de,sE:()=>G,u4:()=>R,vM:()=>se,wB:()=>De,xV:()=>te,yR:()=>q});var r=n(5004),u=function(e,t){if(null==e)throw new TypeError("Cannot convert undefined or null to object");return Object.prototype.hasOwnProperty.call(Object(e),t)};const i={},o=Array.prototype,s=Object.prototype,a=Function.prototype,c=o.slice,l=o.concat,d=s.toString,f=s.hasOwnProperty,D=o.map,p=o.reduce,h=o.forEach,g=o.filter,m=o.every,y=o.some,C=o.indexOf,F=Array.isArray,v=Object.keys,A=a.bind,E=window.isFinite,b=function(e,t){return f.call(e,t)},w=function(e){return e===Object(e)},B=function(e){if(!w(e))return[];if(v)return v(e);const t=[];for(const n in e)b(e,n)&&t.push(n);return t},k=function(e,t,n){let r,u;if(null==e)return e;if(h&&e.forEach===h)e.forEach(t,n);else if(e.length===Number(e.length)){for(r=0,u=e.length;r<u;r++)if(t.call(n,e[r],r,e)===i)return}else{const o=B(e);for(r=0,u=o.length;r<u;r++)if(t.call(n,e[o[r]],o[r],e)===i)return}return e},j=k,P=[];k(["Function","String","Number","Date","RegExp"],(function(e){P[e]=function(t){return d.call(t)==`[object ${e}]`}}));const S=P.Date,O=P.RegExp,x=P.Function,_=P.Number,T=P.String,I=F||function(e){return"[object Array]"==d.call(e)},N=function(e){return _(e)&&e!=Number(e)},Z=function(e,t,n){const r=[];return null==e?r:D&&e.map===D?e.map(t,n):(k(e,(function(e,u,i){r.push(t.call(n,e,u,i))})),r)},L=Z,M=function(){},$=function(e,t,...n){if(A&&e.bind===A)return A.apply(e,[t].concat(n));if(!x(e))throw new TypeError;const r=function(...u){if(!(this instanceof r))return e.apply(t,n.concat(u));M.prototype=e.prototype;const i=new M;M.prototype=null;const o=e.apply(i,n.concat(u));return Object(o)===o?o:i};return r},R=function(e,t,n,r){let u=arguments.length>2;if(null==e&&(e=[]),p&&e.reduce===p)return r&&(t=$(t,r)),u?e.reduce(t,n):e.reduce(t);if(k(e,(function(e,i,o){u?n=t.call(r,n,e,i,o):(n=e,u=!0)})),!u)throw new TypeError("Reduce of empty array with no initial value");return n},U=R,z=R,q=function(e){return e},V=function(e,t,n){t||(t=q);let r=!1;return null==e?r:y&&e.some===y?e.some(t,n):(k(e,(function(e,u,o){if(r||(r=t.call(n,e,u,o)))return i})),Boolean(r))},H=V,G=function(e,t,n){let r;return V(e,(function(e,u,i){if(t.call(n,e,u,i))return r=e,!0})),r},K=G,W=function(e,t,n){const r=[];return null==e?r:g&&e.filter===g?e.filter(t,n):(k(e,(function(e,u,i){t.call(n,e,u,i)&&r.push(e)})),r)},Q=W,J=function(e,t,n){t||(t=q);let r=!0;return null==e?r:m&&e.every===m?e.every(t,n):(k(e,(function(e,u,o){if(!(r=r&&t.call(n,e,u,o)))return i})),Boolean(r))},X=J,Y=function(e){return null==e?0:e.length===Number(e.length)?e.length:B(e).length},ee=function(e,t){let n;return function(...r){return--e>0&&(n=t.apply(this,r)),e<=1&&(t=null),n}};P.Function=function(e){return"function"==typeof e};const te=function(e){return E(e)&&!N(parseFloat(e))},ne=function(e){return!0===e||!1===e||"[object Boolean]"==d.call(e)},re=function(e){return void 0===e},ue=function(e){return function(t){return t[e]}},ie=function(e){return null==e?q:x(e)?e:ue(e)},oe=function(e){return function(t,n,r){const u={};return n=ie(n),k(t,(function(i,o){const s=n.call(r,i,o,t);e(u,s,i)})),u}},se=oe((function(e,t,n){b(e,t)?e[t].push(n):e[t]=[n]})),ae=oe((function(e,t,n){e[t]=n})),ce=function(e,t,n,r){const u=(n=ie(n)).call(r,t);let i=0,o=e.length;for(;i<o;){const t=i+o>>>1;n.call(r,e[t])<u?i=t+1:o=t}return i},le=function(e,t,n){if(null==e)return-1;let r=0;const u=e.length;if(n){if("number"!=typeof n)return r=ce(e,t),e[r]===t?r:-1;r=n<0?Math.max(0,u+n):n}if(C&&e.indexOf===C)return e.indexOf(t,n);for(;r<u;r++)if(e[r]===t)return r;return-1},de=function(e,t){return null!=e&&(e.length!==Number(e.length)&&(e=function(e){const t=B(e),n=B.length,r=Array(n);for(let u=0;u<n;u++)r[u]=e[t[u]];return r}(e)),le(e,t)>=0)},fe=de,De=function(e){return function(t){if(t===e)return!0;for(const n in e)if(e[n]!==t[n])return!1;return!0}},pe=function(e,t){return W(e,De(t))},he=function(e,t){return G(e,De(t))},ge=function(e,...t){const n=l.apply(o,t);return W(e,(function(e){return!de(n,e)}))},me=function(e,...t){return function(...n){let r=0;const u=t.slice();for(let e=0,t=u.length;e<t;e++)b(u[e],"partial")&&(u[e]=n[r++]);for(;r<arguments.length;)u.push(n[r++]);return e.apply(this,u)}},ye=me(ee,2),Ce=function(e,t,...n){return setTimeout((function(){return e.apply(null,n)}),t)},Fe=me(Ce,{partial:me},1),ve=r.z,Ae=function(e,t,n){let r,u,i,o=null,s=0;n||(n={});const a=function(){s=!1===n.leading?0:ve(),o=null,i=e.apply(r,u),r=u=null};return function(...c){const l=ve();s||!1!==n.leading||(s=l);const d=t-(l-s);return r=this,u=c,d<=0?(clearTimeout(o),o=null,s=l,i=e.apply(r,u),r=u=null):o||!1===n.trailing||(o=setTimeout(a,d)),i}},Ee=function(e){const t={},n=B(e);for(let r=0,u=n.length;r<u;r++)t[e[n[r]]]=n[r];return t},be=function(e,...t){return k(t,(function(t){if(t)for(const n in t)void 0===e[n]&&(e[n]=t[n])})),e},we=Object.assign||function(e,...t){return k(t,(function(t){if(t)for(const n in t)u(t,n)&&(e[n]=t[n])})),e},Be=function(e,...t){const n={};return t=[].concat(...t),k(t,(function(t){t in e&&(n[t]=e[t])})),n},ke=function(e){return function(){return e}},je=e=>_(e)&&!N(e),Pe={after:function(e,t){return function(...n){if(--e<1)return t.apply(this,n)}},all:J,any:V,before:ee,bind:$,clone:function(e){return w(e)?I(e)?e.slice():we({},e):e},collect:L,compact:function(e){return W(e,q)},constant:ke,contains:de,debounce:(e,t=100)=>{let n;return function(...r){clearTimeout(n),n=setTimeout((()=>{e.apply(this,r)}),t)}},defaults:be,defer:Fe,delay:Ce,detect:K,difference:ge,each:k,every:X,extend:we,filter:W,find:G,findWhere:he,foldl:U,forEach:j,groupBy:se,has:b,identity:q,include:fe,indexBy:ae,indexOf:le,inject:z,invert:Ee,isArray:I,isBoolean:ne,isDate:S,isFinite:te,isFunction:x,isNaN:N,isNull:function(e){return null===e},isNumber:_,isObject:w,isRegExp:O,isString:T,isUndefined:re,isValidNumber:je,keys:B,last:function(e,t,n){if(null!=e)return null==t||n?e[e.length-1]:c.call(e,Math.max(e.length-t,0))},map:Z,matches:De,max:function(e,t,n){if(!t&&I(e)&&e[0]===Number(e[0])&&e.length<65535)return Math.max(...e);let r=-1/0,u=-1/0;return k(e,(function(e,i,o){const s=t?t.call(n,e,i,o):e;s>u&&(r=e,u=s)})),r},memoize:function(e,t){const n={};return t||(t=q),function(...r){const u=t.apply(this,r);return b(n,u)?n[u]:n[u]=e.apply(this,r)}},now:ve,omit:function(e,...t){const n={};for(const r in e)de(t,r)||(n[r]=e[r]);return n},once:ye,partial:me,pick:Be,pluck:function(e,t){return Z(e,ue(t))},property:ue,propertyOf:function(e){return null==e?function(){}:function(t){return e[t]}},reduce:R,reject:function(e,t,n){return W(e,(function(e,r,u){return!t.call(n,e,r,u)}),n)},result:function(e,t){if(null==e)return;const n=e[t];return x(n)?n.call(e):n},select:Q,size:Y,some:H,sortedIndex:ce,throttle:Ae,where:pe,without:function(e,...t){return ge(e,t)}}},5950:(e,t,n)=>{"use strict";n.d(t,{O9:()=>s,_N:()=>o,kd:()=>l,ke:()=>a,vl:()=>i});const r=/^[^:/?#]+:?\/\/[^/?#]+/,u=e=>{if(e)return new URL(e,window.location)},i=function(e){if(!e)return{};const t=u(e),n={};for(const e of t.searchParams.keys())if(!n[e]){const r=t.searchParams.getAll(e);n[e]=1===r.length?r[0]:r}return n},o=function(e){if(!e)return-1;const t=new URLSearchParams(e).get("jw_start")||-1;return isNaN(t)||t<-1?-1:Number(t)},s=function(e,t="{seek_to_second_number}"){if(!e)return;const n=new URL(e);n.searchParams.set("jw_start","");let r=n.toString();return r=r.replace(/jw_start=?/i,`jw_start=${t}`),r},a=(e,t)=>{if(e)return new URLSearchParams(e).has(t)},c=e=>!!e&&null!==e.match(r),l=(e,t)=>{if(t||(t=document.location.href),!e||!c(t))return"";if(c(e))return e;return new URL(e,t).toString()}},7034:(e,t,n)=>{"use strict";var r,u;n.r(t),n.d(t,{exists:()=>o,isDeepKeyCompliant:()=>f,isFileProtocol:()=>a,isHTTPS:()=>s,isRtmp:()=>c,isYouTube:()=>l,typeOf:()=>d});const i=(null==(r=window)||null==(u=r.location)?void 0:u.protocol)||"",o=e=>{switch(typeof e){case"string":return e.length>0;case"object":return null!==e;case"undefined":return!1;default:return!0}},s=()=>"https:"===i,a=()=>"file:"===i,c=(e,t)=>0===e.indexOf("rtmp:")||"rtmp"===t,l=(e,t)=>"youtube"===t||/^(http|\/\/).*(youtube\.com|youtu\.be)\/.+/.test(e),d=e=>{if(null===e)return"null";const t=typeof e;return"object"===t&&Array.isArray(e)?"array":t},f=(e,t,n)=>{const r=Object.keys(e);return Object.keys(t).length>=r.length&&r.every((r=>{const u=e[r],i=t[r];return u&&"object"==typeof u?!(!i||"object"!=typeof i)&&f(u,i,n):n(r,e)}))}},9025:(e,t,n)=>{"use strict";n.d(t,{Z:()=>r});const r=document.createElement("video")},6601:(e,t,n)=>{"use strict";n.d(t,{i:()=>r});const r="8.38.8+commercial_master.8.@jwplayer/service-loader@2.0.2.ads-dai@mono.ads-freewheel@mono.ads-googima@mono.ads-vast@mono.hls.js@1.6.5.jwplayer@mono.jwplayer-ads-header-bidding@https://gitlab.com/jwpconnatix/jwplayer/web-header-bidding#v7.10.1.jwplayer-analytics@https://gitlab.com/jwpconnatix/jwplayer/web-analytics#github-gitlab.plugin-gapro@mono"},4225:(e,t,n)=>{"use strict";n.d(t,{Z:()=>o});const r=(e,t,n,r)=>`<div id="${e}" class="jw-error jw-reset"><div class="jw-error-msg jw-info-overlay jw-reset"><style>[id="${e}"].jw-error{background:#000;overflow:hidden;position:relative}[id="${e}"] .jw-error-msg{top:50%;left:50%;position:absolute;transform:translate(-50%,-50%)}[id="${e}"] .jw-error-text{text-align:start;color:#FFF;font:14px/1.35 Arial,Helvetica,sans-serif}</style><div class="jw-icon jw-reset"></div><div class="jw-info-container jw-reset"><div class="jw-error-text jw-reset-text" dir="auto" data-nosnippet>${t||""}<span class="jw-break jw-reset"></span>${r?`(${n}: ${r})`.replace(/\s+/g,"&nbsp;"):""}</div></div></div></div>`;var u=n(2799),i=n(974);function o(e,t){const{message:n,code:o}=t,s=r(e.get("id"),n,e.get("localization").errors.errorCode,o.toString()),a=e.get("width"),c=e.get("height"),l=(0,u.az)(s);return(0,i.oB)(l,{width:a.toString().indexOf("%")>0?a:`${a}px`,height:c.toString().indexOf("%")>0?c:`${c}px`}),l}},9926:(e,t,n)=>{"use strict";n.d(t,{Z:()=>c});var r=n(1776),u=n(2799),i=n(974);const o=[];let s=-1;const a=()=>{(0,r.W)(s),s=(0,r.U)((()=>{o.forEach((e=>{e.view.updateBounds();const t=e.view.model.get("containerWidth");e.resized=e.width!==t,e.width=t})),o.forEach((e=>{e.contractElement.scrollLeft=2*e.width})),o.forEach((e=>{(0,i.oB)(e.expandChild,{width:e.width+1}),e.resized&&e.view.model.get("visibility")&&e.view.updateStyles()})),o.forEach((e=>{e.expandElement.scrollLeft=e.width+1})),o.forEach((e=>{e.resized&&e.view.checkResized()}))}))};class c{constructor(e,t,n){const r={display:"block",position:"absolute",top:0,left:0},s={width:"100%",height:"100%"},c=(0,u.az)('<div style="opacity:0;visibility:hidden;overflow:hidden;"><div><div style="height:1px;"></div></div><div class="jw-contract-trigger"></div></div>'),l=c.firstChild,d=l.firstChild,f=l.nextSibling;(0,i.oB)([l,f],Object.assign({overflow:"auto"},r,s)),(0,i.oB)(c,Object.assign({},r,s)),this.expandElement=l,this.expandChild=d,this.contractElement=f,this.hiddenElement=c,this.element=e,this.view=t,this.model=n,this.width=0,this.resized=!1,e.firstChild?e.insertBefore(c,e.firstChild):e.appendChild(c),e.addEventListener("scroll",a,!0),o.push(this),a()}destroy(){if(this.view){const e=o.indexOf(this);-1!==e&&o.splice(e,1),this.element.removeEventListener("scroll",a,!0),this.element.removeChild(this.hiddenElement),this.view=this.model=null}}}},4671:(e,t,n)=>{"use strict";n.d(t,{Z:()=>p});var r=n(6875);const u=[],i=[],o=[],s={};let a,c=!1;const l=(e,t)=>{for(let n=t.length;n--;){const r=t[n];if(e.target===r.getContainer()){r.setIntersection(e);break}}},d=()=>{u.forEach((e=>{e.model.set("activeTab",(0,r.Z)())}))},f=(e,t)=>{const n=t.indexOf(e);-1!==n&&t.splice(n,1)},D=e=>{o.forEach((t=>{t(e)}))};document.addEventListener("visibilitychange",d),document.addEventListener("webkitvisibilitychange",d);const p={add(e){u.push(e)},remove(e){f(e,u),document.removeEventListener("visibilitychange",d),document.removeEventListener("webkitvisibilitychange",d),window.removeEventListener("scroll",D)},addScrollHandler(e){c||(c=!0,window.addEventListener("scroll",D)),o.push(e)},removeScrollHandler(e){const t=o.indexOf(e);-1!==t&&o.splice(t,1)},addWidget(e){i.push(e)},removeWidget(e){f(e,i)},size:()=>u.length,observe(e){(()=>{const e=window.IntersectionObserver;a||(a=new e((e=>{if(null!=e&&e.length)for(let t=e.length;t--;){const n=e[t];l(n,u),l(n,i)}}),{threshold:[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1]}))})(),s[e.id]||(s[e.id]=!0,a.observe(e))},unobserve(e){a&&s[e.id]&&(delete s[e.id],a.unobserve(e))}}},2445:(e,t,n)=>{"use strict";n.d(t,{ZP:()=>v,qG:()=>F});var r=n(5083),u=n(1569),i=n(6042),o=n(7034),s=n(6577),a=n(6599),c=n(386);const l="__CONTEXTUAL__",d=(e,t)=>{const n=e.querySelector(t);if(n)return n.getAttribute("content")};var f=n(4737),D=n.n(f),p=n(67),h=n(3487);const g=e=>"string"==typeof e&&/^\/\/(?:content\.jwplatform|cdn\.jwplayer)\.com\//.test(e),m=e=>`https:${e}`,y=e=>{const t=(0,c.Z)(e.edition),n=e.related,r=!t("discovery")||n!==Object(n),u=!n||"none"!==n.displayMode,i=n||{};let o=void 0===i.oncomplete?"none":i.oncomplete,s=i.autoplaytimer;!1===o||e.repeat?o="hide":"none"===o&&(s=0);const a="autoplay"===o&&s<=0||"none"===o;return Object.assign({},n,{disableRelated:r,showButton:u,oncomplete:o,autoplaytimer:s,shouldAutoAdvance:a})},C=(e,t,n)=>{if(t){e[t.client||(0,h.sb)(n)]=t,delete t.client}},F=e=>{const t=Object.assign({},e.plugins),n=(0,c.Z)(e.edition);if(n("ads")){const n=Object.assign({},e.advertising),r=n.client;if(r){t[(0,h.sb)(r)||r]=n,delete n.client}n.bids&&C(t,n.bids,"bidding")}if(n("jwpsrv")){let n=e.analytics;n!==Object(n)&&(n={}),C(t,n,"jwpsrv")}return C(t,e.ga,"gapro"),C(t,e.interactive,"interactive"),C(t,e.keepWatching,"keepWatching"),t},v=function(e,t){var c;let f=(0,r.ZP)(e,t);const h=f.key||s.default.key,C=new a.ZP(h),v=C.edition();if("free"===C.edition()&&(f=Object.assign({skin:{active:"#ff0046",timeslider:{progress:"none"}},logo:{position:"control-bar",file:D()}},r.ke,(0,i.ei)(f,["analytics","aspectratio","base","file","height","playlist","sources","timeSlider","width"]))),f.key=h,f.edition=v,f.error=C.error(),f.generateSEOMetadata=f.generateSEOMetadata||!1,null!=(c=f).enableVideoThumbnails||(c.enableVideoThumbnails=!0),"unlimited"===v){const e=(0,u.getScriptPath)("jwplayer.js");if(!e)throw new Error("Error setting up player: Could not locate jwplayer.js script tag");n.p=e}var A,E,b;if(f.related=y(f),f.ab&&(f.ab=(e=>{let t=e.ab;return t.clone&&(t=t.clone()),Object.keys(t.tests).forEach((n=>{t.tests[n].forEach((t=>{t.addConfig&&t.addConfig(e,t.selection)}))})),t})(f)),f.plugins=F(f),A=f.playlist,(0,i.HD)(A)&&A.indexOf(l)>-1&&(f.playlist=((e,t)=>{var n;const r=null==e||null==e.querySelector||null==(n=e.querySelector("title"))?void 0:n.textContent,u=d(e,'meta[property="og:title"]');let i=encodeURIComponent(u||r||"");const o=d(e,'meta[property="og:description"]')||d(e,'meta[name="description"]');return o&&(i+=`&page_description=${encodeURIComponent(o)}`),t.replace(l,i)})(document,f.playlist),f.contextual=!0),(0,o.isFileProtocol)()){const{playlist:e,related:t}=f;g(e)&&(f.playlist=m(e)),t&&g(t.file)&&(t.file=m(t.file))}return f.__abSendDomainToFeeds&&(b=f.playlist,/\.jwplatform.com|\.jwplayer.com/.test(b))&&(f.playlist=(E=f.playlist)+`${-1!==E.indexOf("?")?"&":"?"}page_domain=${encodeURIComponent((0,p.X)())}`),f}},6577:(e,t,n)=>{"use strict";n.d(t,{default:()=>re});var r=n(1096),u=n.n(r);window.Promise||(window.Promise=u());var i=n(1569),o=n(6391),s=n(2963),a=n(670);const c={availableProviders:s.B,registerProvider:a.Z};var l=n(4425);c.registerPlugin=function(e,t,n){"jwpsrv"!==e&&(0,l.fo)(e,t,n)};const d=c;var f=n(6601),D=n(4742),p=n(8348),h=n(9750),g=n(1643),m=n(7411),y=n(328),C=n(3487);const F=[["vastxml","adtag","schedules"]],v={googima:F,vast:F,cnx:F},A=(e,t)=>{const n=e.getPlugin(t),r=Object.keys(v);if(-1===r.indexOf(t))throw new Error(`destroyDynamicPlugin must be called with plugins with one of the following plugins: ${r.toString()}`);if(!n)return;if(n.resize&&e.off("resize",n.resizeHandler),delete e.plugins[t],n.destroy)try{n.destroy()}catch(t){e.utils.logger.debug("jwplayer/plugins/dynamic-plugins: ",t)}const u=n.div;null!=u&&u.parentElement&&u.parentElement.removeChild(u),e.trigger("pluginDestroyed",{type:"pluginDestroyed",name:t})},E=(e,t,n,r)=>{const u=(0,C.Nq)(t),i=Object.keys(v),o=((e,t)=>{if(t[e])return t[e];const n=(0,C.sb)(e);if(t[n])return t[n];const r=(0,C.Nq)(e);return t[r]?t[r]:{}})(t,r);if(-1===i.indexOf(u))throw new Error(`setupDynamicPlugin must be called with plugins with one of the following plugins: ${i.toString()}`);A(e,u);const s=((e,t,n)=>{const r=Object.assign({},e),u=Object.assign({},t),i=Object.keys(u).filter((e=>null===e));return i.forEach((e=>delete r[e])),i.forEach((e=>delete u[e])),n.forEach((e=>{e.some((e=>u[e]))&&e.forEach((e=>delete r[e]))})),Object.assign({},r,u)})(o,n,v[u]);return(0,l.Ve)(t,s,e)};var b=n(8494),w=n(6042),B=n(8762);let k=0;const j=function(e,t){const n=new h.ZP(t);return n.on(g.Rc,(t=>{e._qoe.tick("ready"),t.setupTime=e._qoe.between("setup","ready")})),n.on("all",((t,n)=>{e.trigger(t,n)})),n},P=function(e,t){const n=e.plugins,r=Object.keys(n).map((e=>{const t=n[e];return delete n[e],t})),u=e.utils.logger.child("jwplayer/api/api");t.get("setupConfig")&&e.trigger("remove"),e.off(),t.playerDestroy(),r.forEach((e=>{if(e.reset)try{e.reset()}catch(e){u.debug(e)}else if(e.destroy)try{e.destroy()}catch(e){u.debug(e)}})),t.getContainer().removeAttribute("data-jwplayer-id")};function S(e){const t=++k,n=e.id||`player-${t}`,r=new m.Z,u={},i=new B.Z(`JWPlayer[${n}]`);let s=j(this,e);r.tick("init"),e.setAttribute("data-jwplayer-id",n),Object.defineProperties(this,{id:{enumerable:!0,get:()=>n},uniqueId:{enumerable:!0,get:()=>t},plugins:{enumerable:!0,get:()=>u},_qoe:{enumerable:!0,get:()=>r},version:{enumerable:!0,get:()=>f.i},Events:{enumerable:!0,get:()=>y.ZP},utils:{enumerable:!0,get:()=>Object.assign({},b.Z,{logger:i})},_:{enumerable:!0,get:()=>w.ZP}}),Object.assign(this,{_events:{},setup(t){return r.clear("ready"),r.tick("setup"),s&&P(this,s),s=j(this,e),s.init(t,this),this.on(t.events,null,this)},remove(){return this.getPip()&&this.setPip(!1),function(e){for(let t=o.Z.length;t--;)if(o.Z[t].uniqueId===e.uniqueId){o.Z.splice(t,1);break}}(this),s&&P(this,s),Object.keys(u).forEach((e=>{delete u[e]})),this},qoe(){const e=s.getItemQoe();return{setupTime:this._qoe.between("setup","ready"),firstFrame:e.getFirstFrame?e.getFirstFrame():null,player:this._qoe.dump(),item:e.dump()}},addCues(e){return Array.isArray(e)&&s.addCues(e),this},getAudioTracks:()=>s.getAudioTracks(),getBuffer:()=>s.get("buffer"),getCaptions:()=>s.get("captions"),getCaptionsList:()=>s.getCaptionsList(),getConfig:()=>s.getConfig(),getContainer:()=>s.getContainer(),getControls:()=>s.get("controls"),getCues:()=>s.getCues(),getCurrentAudioTrack:()=>s.getCurrentAudioTrack(),getCurrentCaptions:()=>s.getCurrentCaptions(),getCurrentQuality:()=>s.getCurrentQuality(),getCurrentTime:()=>s.get("currentTime"),getAbsolutePosition:()=>s.getAbsolutePosition(),getDuration:()=>s.get("duration"),getEnvironment:()=>p,getFullscreen:()=>s.get("fullscreen"),getHeight:()=>s.getHeight(),getItemMeta:()=>s.get("itemMeta")||{},getMute:()=>s.getMute(),getContainerPercentViewable:()=>s.get("intersectionRatio"),getPercentViewable:()=>s.get("visibility"),getPip:()=>s.get("pip"),getPlaybackRate:()=>s.get("playbackRate"),getPlaylist:()=>s.get("playlist"),getPlaylistIndex:()=>s.get("item"),getPlaylistItem(e){if(!b.Z.exists(e))return s.get("playlistItem");const t=this.getPlaylist();return t?t[e]:null},getPosition:()=>s.get("position"),getProvider:()=>s.getProvider(),getQualityLevels:()=>s.getQualityLevels(),getSafeRegion:(e=!0)=>s.getSafeRegion(e),getState:()=>s.getState(),getStretching:()=>s.get("stretching"),getContainerViewable:()=>s.get("containerViewable"),getViewable:()=>s.get("viewable"),getVisualQuality:()=>s.getVisualQuality(),getVolume:()=>s.get("volume"),getWidth:()=>s.getWidth(),isReady:()=>s.isReady(),setCaptions(e){return s.setCaptions(e),this},setConfig(e){return s.setConfig(e),this},setControls(e){return s.setControls(e),this},setCurrentAudioTrack(e){s.setCurrentAudioTrack(e)},setCurrentCaptions(e){s.setCurrentCaptions(e)},setCurrentQuality(e){s.setCurrentQuality(e)},setFullscreen(e){return s.setFullscreen(e),this},setAllowFullscreen(e){return s.setAllowFullscreen(e),this},setMute(e){return s.setMute(e),this},setPip(e){return s.setPip(e),this},setPlaybackRate(e){return s.setPlaybackRate(e),this},setPlaylistItem(e,t){return s.setPlaylistItem(e,t),this},setCues(e){return Array.isArray(e)&&s.setCues(e),this},setVolume(e){return s.setVolume(e),this},load(e,t){return s.load(e,t),this},play(e){return s.play(e),this},pause(e){return s.pause(e),this},playToggle(e){switch(this.getState()){case g.r0:case g.Kb:return this.pause(e);default:return this.play(e)}},seek(e,t){return s.seek(e,t),this},playlistItem(e,t){return s.playlistItem(e,t),this},playlistNext(e){return s.playlistNext(e),this},playlistPrev(e){return s.playlistPrev(e),this},next(e){return s.next(e),this},requestPip(e){return s.requestPip(e),this},castToggle(){return s.castToggle(),this},stopCasting(){return s.stopCasting(),this},requestCast(e){return s.requestCast(e),this},createInstream:()=>s.createInstream(),stop(){return s.stop(),this},resize(e,t){return s.resize(e,t),this},addButton(e,t,n,r,u){return s.addButton(e,t,n,r,u),this},removeButton(e){return s.removeButton(e),this},getMediaElement:()=>s.getMediaElement(),attachMedia(){return s.attachMedia(),this},detachMedia(){return s.detachMedia(),this},isBeforeComplete:()=>s.isBeforeComplete(),isBeforePlay:()=>s.isBeforePlay(),setPlaylistItemCallback(e,t){s.setItemCallback(e,t)},removePlaylistItemCallback(){s.setItemCallback(null)},getPlaylistItemPromise:e=>s.getItemPromise(e),getFloating:()=>Boolean(s.get("isFloating")),setFloating(e){s.setConfig({floating:{mode:e?"always":"never"}})},getChapters:()=>s.getChapters(),getCurrentChapter:()=>s.getCurrentChapter(),setChapter:e=>s.setChapter(e),setupDynamicPlugin(e,t){return e?E(this,e,t,s.get("plugins")):Promise.resolve()},destroyDynamicPlugin(e){if(e)return A(this,e)}})}Object.assign(S.prototype,{on(e,t,n){return y.on.call(this,e,t,n)},once(e,t,n){return y.IH.call(this,e,t,n)},off(e,t,n){return y.S1.call(this,e,t,n)},trigger(e,t){return(t=w.ZP.isObject(t)?Object.assign({},t):{}).type=e,D.Z.debug?y.X$.call(this,e,t):y.wj.call(this,e,t)},getPlugin(e){return this.plugins[e]},addPlugin(e,t){this.plugins[e]=t,"function"==typeof t.addToPlayer&&(this.isReady()?t.addToPlayer.call(this,!0):this.on("ready",(function(){t.addToPlayer.call(this,!1)}))),t.resize&&this.on("resize",t.resizeHandler)},registerPlugin(e,t,n){(0,l.fo)(e,t,n)},getAdBlock:()=>!1,playAd(e){},pauseAd(e){},skipAd(){},setAdMacros(e){},getAdMacros(){},updateQueryJSAdTargeting(e){},getQueryJSAdTargeting(){}}),n.p=(0,i.loadFrom)();const O=e=>{for(let t=0;t<o.Z.length;t++)if(o.Z[t].id===e)return o.Z[t];return null},x=function(e){let t,n;if(e?"string"==typeof e?(t=O(e),t||(n=document.getElementById(e))):"number"==typeof e?t=o.Z[e]:e.nodeType&&(n=e,t=O(n.id||n.getAttribute("data-jwplayer-id"))):t=o.Z[0],t)return t;if(n){const e=new S(n);return o.Z.push(e),e}return{registerPlugin:l.fo}},_=e=>{Object.defineProperties(e,{api:{get:()=>d,set(){}},version:{get:()=>f.i,set(){}},debug:{get:()=>D.Z.debug,set(e){D.Z.debug=Boolean(e)}}})};_(x);const T=x;var I=n(5882),N=n(6599),Z=n(676),L=n(5592),M=n(6769),$=n(9025);const R=w.ZP.extend,U={};U._=w.ZP,U.utils=Object.assign(b.Z,{key:N.ZP,extend:R,scriptloader:Z.ZP,rssparser:{parse:M.Z},tea:L.p,UI:I.ZP}),U.utils.css.style=U.utils.style,U.vid=$.Z;const z=U;var q=n(7543);const V=b.Z.logger.child("api/api-public"),H=/^(?:on(?:ce)?|off|trigger)$/,G=e=>{V.warn(`The API method jwplayer().${e}() is disabled in the free edition of JW Player.`)},K=(e,t,n)=>{try{const r=((e,t)=>{switch(e){case"setup":return Boolean(t);case"getSafeRegion":case"pauseAd":case"setControls":case"setFullscreen":case"setMute":return Boolean(t)===t?t:void 0;case"setPlaylistItem":case"getPlaylistItem":return(0|t)===t?t:void 0;case"setPlaybackRate":case"setVolume":return Number(t);case"setConfig":return Object.keys(Object(t)).join(",");case"on":case"once":case"off":case"trigger":case"getPlugin":case"addPlugin":case"registerPlugin":return`${t}`}return null})(t,n);e.trackExternalAPIUsage(t,r)}catch(e){D.Z.debug&&V.warn(e)}},W=(e,t)=>{if(t.length){const n=e.getPlugin("jwpsrv");null!=n&&n.trackExternalAPIUsage&&(t.forEach((e=>{K(n,e[0],e[1])})),t.length=0)}},Q=(e,t,n,r,u)=>function(...i){const o=i[0],s=t._trackCallQueue||(t._trackCallQueue=[]),a=H.test(n),c=a&&i[1]&&i[1]._callback,l=u.edition||((e,t,n)=>{const r=e.getConfig()[n];return t[n]=r,r})(t,u,"edition");if("free"===l){if(["addButton","addCues","detachMedia","load","next","pause","play","playlistItem","playlistNext","playlistPrev","playToggle","resize","seek","setCaptions","setConfig","setControls","setCues","setFullscreen","setMute","setPlaybackRate","setPlaylistItem","setVolume","stop"].indexOf(n)>-1)return G(n),e;if(["createInstream","setCurrentAudioTrack","setCurrentCaptions","setCurrentQuality"].indexOf(n)>-1)return G(n),null}if(c||s.push([n,o]),a)return W(t,s),t[n].apply(e,i);((e,t)=>{const n={reason:"play"!==e&&"seek"!==e&&"pause"!==e&&(0,q.C)()?"interaction":"external"};switch(e){case"play":case"pause":case"playToggle":case"playlistNext":case"playlistPrev":case"next":t[0]=n;break;case"seek":case"playlistItem":t[1]=n}})(n,i);const d=t[n](...i);return"remove"===n?t.off.call(e):"setup"===n&&(t.off.call(e),t.off(o.events,null,t),t.on.call(e,o.events,null,e),t.on("all",((n,i)=>{if("ready"===n){const n=Object.keys(t).filter((e=>"_"!==e[0]&&-1===r.indexOf(e)&&"function"==typeof t[e])),i=r.concat(n);n.forEach((n=>{e[n]=Q(e,t,n,i,u)}))}t.trigger.call(e,n,i),W(t,s)}))),W(t,s),d===t?e:d},J=["getMediaElement"],X=(e,t,n,r)=>{const u=Object.keys(n);u.forEach((i=>{const o=n[i];-1===J.indexOf(i)&&("function"==typeof o&&"Events"!==i?e[i]=Q(e,t,i,u,r):"_events"===i?e._events={}:Object.defineProperty(e,i,{enumerable:!0,get:()=>n[i]}))}))},Y=function(e){const t={};X(this,e,e,t),X(this,e,S.prototype,t)},ee=window;Object.assign(T,z);const te=function(e){const t=T(e);return t.uniqueId?t._publicApi||(t._publicApi=new Y(t)):t};Object.assign(te,z),_(te),"function"==typeof ee.define&&ee.define.amd&&ee.define([],(function(){return te}));let ne=te;ee.jwplayer&&(ne=ee.jwplayer);const re=ne},4425:(e,t,n)=>{"use strict";n.d(t,{ZP:()=>d,fo:()=>c,Ve:()=>l});var r=n(3487),u=n(4446);const i=function(){this.load=function(e,t,n,i){return n&&"object"==typeof n?Promise.all(Object.keys(n).filter((e=>e)).map((o=>{const s=n[o];return t.setupPlugin(o).then((t=>{if(!i.attributes._destroyed)return(0,r.MK)(t,s,e)})).catch((e=>(t.removePlugin(o),e.code?e:new u.rG(null,(0,r.bX)(o),e))))}))):Promise.resolve()}};var o=n(4101);const s={};const a=new class{setupPlugin(e){const t=this.getPlugin(e);if(t)return t.promise;return this.addPlugin(e).load()}addPlugin(e){const t=(0,r.Nq)(e);let n=s[t];return n||(n=new o.Z(e),s[t]=n),n}getPlugin(e){return s[(0,r.Nq)(e)]}removePlugin(e){delete s[(0,r.Nq)(e)]}getPlugins(){return s}},c=function(e,t,n){const r=a.addPlugin(e);r.js||r.registerPlugin(e,t,n)},l=async(e,t,n)=>{const u=(0,r.Nq)(e),i=a.getPlugin(u);if(i)return n.utils.logger.warn(`'jwplayer/plugins/model JW Plugin "${u}" already loaded from "${i.url}". Ignoring "${e}."`),(0,r.MK)(i,t,n);let o=e;return u===e&&(o=(e=>(0,r.sb)(e)||e)(e)),a.setupPlugin(o).then((e=>(0,r.MK)(e,t,n)))};function d(e,t){const n=e.get("plugins");window.jwplayerPluginJsonp=c;return(e.pluginLoader=e.pluginLoader||new i).load(t,a,n,e).then((t=>{if(!e.attributes._destroyed)return delete window.jwplayerPluginJsonp,t}))}},3487:(e,t,n)=>{"use strict";n.d(t,{MK:()=>r.MK,Nq:()=>r.Nq,bX:()=>u,sb:()=>i});n(1569);var r=n(7164);const u=function(e){let t=(0,r.bX)(e);if(!e)return t;switch((0,r.Nq)(e)){case"jwpsrv":t=305001;break;case"googima":t=305002;break;case"vast":t=305003;break;case"freewheel":t=305004;break;case"dai":t=305005;break;case"gapro":t=305006;break;case"bidding":t=305007}return t},i=e=>{let t="";"https:"!==window.location.protocol&&"http:"!==window.location.protocol&&(t="https:");const n={bidding:"//ssl.p.jwpcdn.com/player/v/8.38.8/bidding.js",jwpsrv:"//ssl.p.jwpcdn.com/player/v/8.38.8/jwpsrv.js",dai:"//ssl.p.jwpcdn.com/player/v/8.38.8/dai.js",vast:"//ssl.p.jwpcdn.com/player/v/8.38.8/vast.js",googima:"//ssl.p.jwpcdn.com/player/v/8.38.8/googima.js",freewheel:"//ssl.p.jwpcdn.com/player/v/8.38.8/freewheel.js",gapro:"//ssl.p.jwpcdn.com/player/v/8.38.8/gapro.js",interactive:"//ssl.p.jwpcdn.com/player/v/8.38.8/interactive.js",keepWatching:"//ssl.p.jwpcdn.com/player/v/8.38.8/keepWatching.js",cnx:"//ssl.p.jwpcdn.com/player/v/8.38.8/cnx.js"}[e];return n?t+n:""}},1918:(e,t,n)=>{"use strict";n.d(t,{Gb:()=>l,d3:()=>d,lD:()=>c,w0:()=>a});var r=n(386);const u=[{configName:"clearkey",keyName:"org.w3.clearkey"},{configName:"widevine",keyName:"com.widevine.alpha"},{configName:"playready",keyName:"com.microsoft.playready"}],i=[],o={};let s;const a=e=>e.some((e=>Boolean(e.drm)||e.sources.some((e=>Boolean(e.drm))))),c=e=>s||((Boolean(navigator.requestMediaKeySystemAccess)&&Boolean(window.MediaKeySystemAccess.prototype.getConfiguration)||Boolean(window.MSMediaKeys))&&(0,r.Z)(e)("drm")?(u.forEach((e=>{const t=(n=e.keyName,r=[{initDataTypes:["cenc"],videoCapabilities:[{contentType:'video/mp4;codecs="avc1.4d401e"'}],audioCapabilities:[{contentType:'audio/mp4;codecs="mp4a.40.2"'}]}],navigator.requestMediaKeySystemAccess?navigator.requestMediaKeySystemAccess(n,r):new Promise(((e,t)=>{let r;try{r=new window.MSMediaKeys(n)}catch(e){return void t(e)}e(r)}))).then((function(){o[e.configName]=!0})).catch((function(){o[e.configName]=!1}));var n,r;i.push(t)})),s=Promise.all(i),s):Promise.resolve()),l=e=>o[e],d=e=>{if(s)return Object.keys(e).some((e=>l(e)))}},2963:(e,t,n)=>{"use strict";n.d(t,{B:()=>g});var r=n(6593),u=n(8348),i=n(386),o=n(1918),s=n(9025);const a=e=>{var t;null!=(t=e)&&t.length&&Array.isArray(e)||(e=['video/mp4;codecs="avc1.4d400d,mp4a.40.2"']);const n=window.MediaSource;return!(!n||!n.isTypeSupported)&&e.every((e=>n.isTypeSupported(e)))},c=e=>/hls|m3u8/.test(((null==e?void 0:e.type)||"").toLowerCase())||((null==e?void 0:e.file)||"").toLowerCase().indexOf(".m3u8")>-1,l=e=>/mpd|dash/.test(((null==e?void 0:e.type)||"").toLowerCase())||((null==e?void 0:e.file)||"").toLowerCase().indexOf("mpd-time-csf")>-1,d=r.B.find((e=>"html5"===e.name)),f=d.supports,D=function(...e){const[t,n]=e,r=f.apply(this,e);if(l(t))return!1;if(r&&t.drm&&c(t)){const e=(0,i.Z)(n)("drm");if(e&&t.drm.fairplay){const e=window.WebKitMediaKeys;return null==e||null==e.isTypeSupported?void 0:e.isTypeSupported("com.apple.fps.1_0","video/mp4")}return e}return r},p=e=>{if(e.drm||!c(e))return!1;const t=Boolean(null==s.Z||null==s.Z.canPlayType?void 0:s.Z.canPlayType("application/vnd.apple.mpegURL")),n="boolean"==typeof(null==e?void 0:e.safarihlsjs)&&e.safarihlsjs;"boolean"!=typeof(null==e?void 0:e.hlsjsdefault)||e.hlsjsdefault,"boolean"!=typeof(null==e?void 0:e.androidhls)||e.androidhls;return(!u.OS.iPad||!u.Browser.chrome)&&(!(t&&u.Browser.safari&&!n)&&((!t||!u.OS.android||!1===e.androidhls||!1!==e.hlsjsdefault)&&a(e.mediaTypes)))},h=e=>!(e.drm&&!(0,o.d3)(e.drm))&&(a(e.mediaTypes)&&(l(e)||c(e)));d.supports=D,r.B.push({name:"shaka",supports:h}),r.B.unshift({name:"hlsjs",supports:p});const g=r.B},2303:(e,t,n)=>{"use strict";n.d(t,{Z:()=>d});var r=n(2963),u=n(12),i=n(670),o=n(2894);const s={html5:()=>n.e(250).then(function(e){const t=n(9181).default;return(0,i.Z)(t),t}.bind(null,n)).catch((0,o.Ep)(152))};Object.assign(s,{shaka:()=>n.e(371).then(function(e){const t=n(2287).default;return(0,i.Z)(t),t}.bind(null,n)).catch((0,o.Ep)(154)),hlsjs:()=>n.e(98).then(function(e){const t=n(9054).default;return(0,i.Z)(t),t}.bind(null,n)).catch((0,o.Ep)(153))});const a=s,c=function(e){this.config=e||{}};Object.assign(c.prototype,{load(e){const t=a[e],n=()=>Promise.reject(new Error("Failed to load media"));return t?t().then((()=>{const t=u.U[e];return t||n()})):n()},providerSupports:(e,t)=>e.supports(t),choose(e){if(e===Object(e)){const t=r.B.length;for(let n=0;n<t;n++){const i=r.B[n];if(this.providerSupports(i,e)){return{priority:t-n-1,name:i.name,type:e.type,providerToCheck:i,provider:u.U[i.name]}}}}return{}}});const l=c;l.prototype.providerSupports=function(e,t){return e.supports(t,this.config.edition)};const d=l},5140:(e,t,n)=>{"use strict";n.d(t,{t:()=>r});const r=window.atob;window.btoa},386:(e,t,n)=>{"use strict";n.d(t,{Z:()=>p});const r="free",u="starter",i="business",o="premium",s="enterprise",a="developer",c="platinum",l="ads",d="unlimited",f="trial",D="invalid";function p(e){const t={setup:[r,u,i,o,s,a,l,d,f,c],drm:[s,a,l,d,f],ads:[l,d,f,c,s,a,i],jwpsrv:[r,u,i,o,s,a,l,f,c,D],discovery:[l,s,a,f,d]};return function(n){return t[n]&&t[n].indexOf(e)>-1}}},7010:(e,t,n)=>{"use strict";n.d(t,{Z:()=>i});var r=n(5950);const u=function(e,t){return e.location!==e.parent.location&&(0,r.ke)(t,"isAMP")};function i(){return u(window,document.location.search)}},560:(e,t,n)=>{"use strict";n.d(t,{Z:()=>u});const r=()=>r._iframe;r.mock=e=>{r._iframe=e},r.unmock=()=>{r._iframe=r._original},r._iframe=window.top!==window.self,r._original=r._iframe;const u=r},6599:(e,t,n)=>{"use strict";n.d(t,{ZP:()=>c,u5:()=>s});var r=n(5592),u=n(386),i=n(5140),o=n(4446);const s=100013,a="invalid";const c=class{constructor(e){this.keyData=(e=>{let t,n,o;try{const s=(0,r.p)(e||"",(0,i.t)("NDh2aU1Cb0NHRG5hcDFRZQ==")).split("/");if(t=s[0],"pro"===t&&(t="premium"),(0,u.Z)(t)("setup")||(t=a),s.length>2){n=s[1];const e=parseInt(s[2],10);e>0&&(o=new Date,o.setTime(e))}}catch(e){t=a}return{edition:t,token:n,expiration:o}})(e),this.edition=function(){return this.keyData.edition},this.token=function(){return this.keyData.token},this.expiration=function(){return this.keyData.expiration},this.duration=function(){return this.keyData.expiration?this.keyData.expiration.getTime()-(new Date).getTime():0},this.error=function(){let t;return void 0===e?t=100011:this.keyData.edition!==a&&this.keyData.token?this.duration()<0&&(t=s):t=100012,t?new o.rG(o.pJ,t):null}}}},67:(e,t,n)=>{"use strict";n.d(t,{X:()=>u});var r=n(560);const u=()=>{let e=window.location.host;if((0,r.Z)()){e=(document.referrer?(e=>{const t=document.createElement("a");return t.href=e,t})(document.referrer):{}).host;try{e=e||window.top.location.host}catch(e){}}return e}},5592:(e,t,n)=>{"use strict";n.d(t,{p:()=>s});var r=n(5140);const u=e=>unescape(encodeURIComponent(e)),i=e=>{const t=new Array(Math.ceil(e.length/4));for(let n=0;n<t.length;n++)t[n]=e.charCodeAt(4*n)+(e.charCodeAt(4*n+1)<<8)+(e.charCodeAt(4*n+2)<<16)+(e.charCodeAt(4*n+3)<<24);return t},o=e=>{const t=new Array(e.length);for(let n=0;n<e.length;n++)t[n]=String.fromCharCode(255&e[n],e[n]>>>8&255,e[n]>>>16&255,e[n]>>>24&255);return t.join("")},s=function(e,t){if(e=String(e),t=String(t),0===e.length)return"";const n=i((0,r.t)(e)),s=i(u(t).slice(0,16)),a=n.length,c=2654435769;let l,d,f=n[a-1],D=n[0],p=Math.floor(6+52/a)*c;for(;p;){d=p>>>2&3;for(let e=a-1;e>=0;e--)f=n[e>0?e-1:a-1],l=(f>>>5^D<<2)+(D>>>3^f<<4)^(p^D)+(s[3&e^d]^f),D=n[e]-=l;p-=c}return(e=>{try{return decodeURIComponent(escape(e))}catch(t){return e}})(o(n).replace(/\0+$/,""))}},1142:function(e){e.exports=function(){"use strict";function e(e,t){return e(t={exports:{}},t.exports),t.exports}var t=e((function(e){var t=e.exports="undefined"!=typeof window&&window.Math==Math?window:"undefined"!=typeof self&&self.Math==Math?self:Function("return this")();"number"==typeof __g&&(__g=t)})),n=e((function(e){var t=e.exports={version:"2.6.5"};"number"==typeof __e&&(__e=t)})),r=(n.version,function(e){return"object"==typeof e?null!==e:"function"==typeof e}),u=function(e){if(!r(e))throw TypeError(e+" is not an object!");return e},i=function(e){try{return!!e()}catch(e){return!0}},o=!i((function(){return 7!=Object.defineProperty({},"a",{get:function(){return 7}}).a})),s=t.document,a=r(s)&&r(s.createElement),c=function(e){return a?s.createElement(e):{}},l=!o&&!i((function(){return 7!=Object.defineProperty(c("div"),"a",{get:function(){return 7}}).a})),d=function(e,t){if(!r(e))return e;var n,u;if(t&&"function"==typeof(n=e.toString)&&!r(u=n.call(e)))return u;if("function"==typeof(n=e.valueOf)&&!r(u=n.call(e)))return u;if(!t&&"function"==typeof(n=e.toString)&&!r(u=n.call(e)))return u;throw TypeError("Can't convert object to primitive value")},f=Object.defineProperty,D={f:o?Object.defineProperty:function(e,t,n){if(u(e),t=d(t,!0),u(n),l)try{return f(e,t,n)}catch(e){}if("get"in n||"set"in n)throw TypeError("Accessors not supported!");return"value"in n&&(e[t]=n.value),e}},p=function(e,t){return{enumerable:!(1&e),configurable:!(2&e),writable:!(4&e),value:t}},h=o?function(e,t,n){return D.f(e,t,p(1,n))}:function(e,t,n){return e[t]=n,e},g={}.hasOwnProperty,m=function(e,t){return g.call(e,t)},y=0,C=Math.random(),F=function(e){return"Symbol(".concat(void 0===e?"":e,")_",(++y+C).toString(36))},v=!1,A=e((function(e){var r="__core-js_shared__",u=t[r]||(t[r]={});(e.exports=function(e,t){return u[e]||(u[e]=void 0!==t?t:{})})("versions",[]).push({version:n.version,mode:v?"pure":"global",copyright:"© 2019 Denis Pushkarev (zloirock.ru)"})})),E=A("native-function-to-string",Function.toString),b=e((function(e){var r=F("src"),u="toString",i=(""+E).split(u);n.inspectSource=function(e){return E.call(e)},(e.exports=function(e,n,u,o){var s="function"==typeof u;s&&(m(u,"name")||h(u,"name",n)),e[n]!==u&&(s&&(m(u,r)||h(u,r,e[n]?""+e[n]:i.join(String(n)))),e===t?e[n]=u:o?e[n]?e[n]=u:h(e,n,u):(delete e[n],h(e,n,u)))})(Function.prototype,u,(function(){return"function"==typeof this&&this[r]||E.call(this)}))})),w=function(e){if("function"!=typeof e)throw TypeError(e+" is not a function!");return e},B=function(e,t,n){if(w(e),void 0===t)return e;switch(n){case 1:return function(n){return e.call(t,n)};case 2:return function(n,r){return e.call(t,n,r)};case 3:return function(n,r,u){return e.call(t,n,r,u)}}return function(){return e.apply(t,arguments)}},k="prototype",j=function(e,r,u){var i,o,s,a,c=e&j.F,l=e&j.G,d=e&j.S,f=e&j.P,D=e&j.B,p=l?t:d?t[r]||(t[r]={}):(t[r]||{})[k],g=l?n:n[r]||(n[r]={}),m=g[k]||(g[k]={});for(i in l&&(u=r),u)s=((o=!c&&p&&void 0!==p[i])?p:u)[i],a=D&&o?B(s,t):f&&"function"==typeof s?B(Function.call,s):s,p&&b(p,i,s,e&j.U),g[i]!=s&&h(g,i,a),f&&m[i]!=s&&(m[i]=s)};t.core=n,j.F=1,j.G=2,j.S=4,j.P=8,j.B=16,j.W=32,j.U=64,j.R=128;var P,S=j,O=Math.ceil,x=Math.floor,_=function(e){return isNaN(e=+e)?0:(e>0?x:O)(e)},T=function(e){if(null==e)throw TypeError("Can't call method on  "+e);return e},I=(P=!1,function(e,t){var n,r,u=String(T(e)),i=_(t),o=u.length;return i<0||i>=o?P?"":void 0:(n=u.charCodeAt(i))<55296||n>56319||i+1===o||(r=u.charCodeAt(i+1))<56320||r>57343?P?u.charAt(i):n:P?u.slice(i,i+2):r-56320+(n-55296<<10)+65536});S(S.P,"String",{codePointAt:function(e){return I(this,e)}}),n.String.codePointAt;var N=Math.max,Z=Math.min,L=function(e,t){return(e=_(e))<0?N(e+t,0):Z(e,t)},M=String.fromCharCode,$=String.fromCodePoint;S(S.S+S.F*(!!$&&1!=$.length),"String",{fromCodePoint:function(e){for(var t,n=arguments,r=[],u=arguments.length,i=0;u>i;){if(t=+n[i++],L(t,1114111)!==t)throw RangeError(t+" is not a valid code point");r.push(t<65536?M(t):M(55296+((t-=65536)>>10),t%1024+56320))}return r.join("")}}),n.String.fromCodePoint;var R,U,z,q,V,H,G,K,W,Q,J,X,Y,ee,te={Space_Separator:/[\u1680\u2000-\u200A\u202F\u205F\u3000]/,ID_Start:/[\xAA\xB5\xBA\xC0-\xD6\xD8-\xF6\xF8-\u02C1\u02C6-\u02D1\u02E0-\u02E4\u02EC\u02EE\u0370-\u0374\u0376\u0377\u037A-\u037D\u037F\u0386\u0388-\u038A\u038C\u038E-\u03A1\u03A3-\u03F5\u03F7-\u0481\u048A-\u052F\u0531-\u0556\u0559\u0561-\u0587\u05D0-\u05EA\u05F0-\u05F2\u0620-\u064A\u066E\u066F\u0671-\u06D3\u06D5\u06E5\u06E6\u06EE\u06EF\u06FA-\u06FC\u06FF\u0710\u0712-\u072F\u074D-\u07A5\u07B1\u07CA-\u07EA\u07F4\u07F5\u07FA\u0800-\u0815\u081A\u0824\u0828\u0840-\u0858\u0860-\u086A\u08A0-\u08B4\u08B6-\u08BD\u0904-\u0939\u093D\u0950\u0958-\u0961\u0971-\u0980\u0985-\u098C\u098F\u0990\u0993-\u09A8\u09AA-\u09B0\u09B2\u09B6-\u09B9\u09BD\u09CE\u09DC\u09DD\u09DF-\u09E1\u09F0\u09F1\u09FC\u0A05-\u0A0A\u0A0F\u0A10\u0A13-\u0A28\u0A2A-\u0A30\u0A32\u0A33\u0A35\u0A36\u0A38\u0A39\u0A59-\u0A5C\u0A5E\u0A72-\u0A74\u0A85-\u0A8D\u0A8F-\u0A91\u0A93-\u0AA8\u0AAA-\u0AB0\u0AB2\u0AB3\u0AB5-\u0AB9\u0ABD\u0AD0\u0AE0\u0AE1\u0AF9\u0B05-\u0B0C\u0B0F\u0B10\u0B13-\u0B28\u0B2A-\u0B30\u0B32\u0B33\u0B35-\u0B39\u0B3D\u0B5C\u0B5D\u0B5F-\u0B61\u0B71\u0B83\u0B85-\u0B8A\u0B8E-\u0B90\u0B92-\u0B95\u0B99\u0B9A\u0B9C\u0B9E\u0B9F\u0BA3\u0BA4\u0BA8-\u0BAA\u0BAE-\u0BB9\u0BD0\u0C05-\u0C0C\u0C0E-\u0C10\u0C12-\u0C28\u0C2A-\u0C39\u0C3D\u0C58-\u0C5A\u0C60\u0C61\u0C80\u0C85-\u0C8C\u0C8E-\u0C90\u0C92-\u0CA8\u0CAA-\u0CB3\u0CB5-\u0CB9\u0CBD\u0CDE\u0CE0\u0CE1\u0CF1\u0CF2\u0D05-\u0D0C\u0D0E-\u0D10\u0D12-\u0D3A\u0D3D\u0D4E\u0D54-\u0D56\u0D5F-\u0D61\u0D7A-\u0D7F\u0D85-\u0D96\u0D9A-\u0DB1\u0DB3-\u0DBB\u0DBD\u0DC0-\u0DC6\u0E01-\u0E30\u0E32\u0E33\u0E40-\u0E46\u0E81\u0E82\u0E84\u0E87\u0E88\u0E8A\u0E8D\u0E94-\u0E97\u0E99-\u0E9F\u0EA1-\u0EA3\u0EA5\u0EA7\u0EAA\u0EAB\u0EAD-\u0EB0\u0EB2\u0EB3\u0EBD\u0EC0-\u0EC4\u0EC6\u0EDC-\u0EDF\u0F00\u0F40-\u0F47\u0F49-\u0F6C\u0F88-\u0F8C\u1000-\u102A\u103F\u1050-\u1055\u105A-\u105D\u1061\u1065\u1066\u106E-\u1070\u1075-\u1081\u108E\u10A0-\u10C5\u10C7\u10CD\u10D0-\u10FA\u10FC-\u1248\u124A-\u124D\u1250-\u1256\u1258\u125A-\u125D\u1260-\u1288\u128A-\u128D\u1290-\u12B0\u12B2-\u12B5\u12B8-\u12BE\u12C0\u12C2-\u12C5\u12C8-\u12D6\u12D8-\u1310\u1312-\u1315\u1318-\u135A\u1380-\u138F\u13A0-\u13F5\u13F8-\u13FD\u1401-\u166C\u166F-\u167F\u1681-\u169A\u16A0-\u16EA\u16EE-\u16F8\u1700-\u170C\u170E-\u1711\u1720-\u1731\u1740-\u1751\u1760-\u176C\u176E-\u1770\u1780-\u17B3\u17D7\u17DC\u1820-\u1877\u1880-\u1884\u1887-\u18A8\u18AA\u18B0-\u18F5\u1900-\u191E\u1950-\u196D\u1970-\u1974\u1980-\u19AB\u19B0-\u19C9\u1A00-\u1A16\u1A20-\u1A54\u1AA7\u1B05-\u1B33\u1B45-\u1B4B\u1B83-\u1BA0\u1BAE\u1BAF\u1BBA-\u1BE5\u1C00-\u1C23\u1C4D-\u1C4F\u1C5A-\u1C7D\u1C80-\u1C88\u1CE9-\u1CEC\u1CEE-\u1CF1\u1CF5\u1CF6\u1D00-\u1DBF\u1E00-\u1F15\u1F18-\u1F1D\u1F20-\u1F45\u1F48-\u1F4D\u1F50-\u1F57\u1F59\u1F5B\u1F5D\u1F5F-\u1F7D\u1F80-\u1FB4\u1FB6-\u1FBC\u1FBE\u1FC2-\u1FC4\u1FC6-\u1FCC\u1FD0-\u1FD3\u1FD6-\u1FDB\u1FE0-\u1FEC\u1FF2-\u1FF4\u1FF6-\u1FFC\u2071\u207F\u2090-\u209C\u2102\u2107\u210A-\u2113\u2115\u2119-\u211D\u2124\u2126\u2128\u212A-\u212D\u212F-\u2139\u213C-\u213F\u2145-\u2149\u214E\u2160-\u2188\u2C00-\u2C2E\u2C30-\u2C5E\u2C60-\u2CE4\u2CEB-\u2CEE\u2CF2\u2CF3\u2D00-\u2D25\u2D27\u2D2D\u2D30-\u2D67\u2D6F\u2D80-\u2D96\u2DA0-\u2DA6\u2DA8-\u2DAE\u2DB0-\u2DB6\u2DB8-\u2DBE\u2DC0-\u2DC6\u2DC8-\u2DCE\u2DD0-\u2DD6\u2DD8-\u2DDE\u2E2F\u3005-\u3007\u3021-\u3029\u3031-\u3035\u3038-\u303C\u3041-\u3096\u309D-\u309F\u30A1-\u30FA\u30FC-\u30FF\u3105-\u312E\u3131-\u318E\u31A0-\u31BA\u31F0-\u31FF\u3400-\u4DB5\u4E00-\u9FEA\uA000-\uA48C\uA4D0-\uA4FD\uA500-\uA60C\uA610-\uA61F\uA62A\uA62B\uA640-\uA66E\uA67F-\uA69D\uA6A0-\uA6EF\uA717-\uA71F\uA722-\uA788\uA78B-\uA7AE\uA7B0-\uA7B7\uA7F7-\uA801\uA803-\uA805\uA807-\uA80A\uA80C-\uA822\uA840-\uA873\uA882-\uA8B3\uA8F2-\uA8F7\uA8FB\uA8FD\uA90A-\uA925\uA930-\uA946\uA960-\uA97C\uA984-\uA9B2\uA9CF\uA9E0-\uA9E4\uA9E6-\uA9EF\uA9FA-\uA9FE\uAA00-\uAA28\uAA40-\uAA42\uAA44-\uAA4B\uAA60-\uAA76\uAA7A\uAA7E-\uAAAF\uAAB1\uAAB5\uAAB6\uAAB9-\uAABD\uAAC0\uAAC2\uAADB-\uAADD\uAAE0-\uAAEA\uAAF2-\uAAF4\uAB01-\uAB06\uAB09-\uAB0E\uAB11-\uAB16\uAB20-\uAB26\uAB28-\uAB2E\uAB30-\uAB5A\uAB5C-\uAB65\uAB70-\uABE2\uAC00-\uD7A3\uD7B0-\uD7C6\uD7CB-\uD7FB\uF900-\uFA6D\uFA70-\uFAD9\uFB00-\uFB06\uFB13-\uFB17\uFB1D\uFB1F-\uFB28\uFB2A-\uFB36\uFB38-\uFB3C\uFB3E\uFB40\uFB41\uFB43\uFB44\uFB46-\uFBB1\uFBD3-\uFD3D\uFD50-\uFD8F\uFD92-\uFDC7\uFDF0-\uFDFB\uFE70-\uFE74\uFE76-\uFEFC\uFF21-\uFF3A\uFF41-\uFF5A\uFF66-\uFFBE\uFFC2-\uFFC7\uFFCA-\uFFCF\uFFD2-\uFFD7\uFFDA-\uFFDC]|\uD800[\uDC00-\uDC0B\uDC0D-\uDC26\uDC28-\uDC3A\uDC3C\uDC3D\uDC3F-\uDC4D\uDC50-\uDC5D\uDC80-\uDCFA\uDD40-\uDD74\uDE80-\uDE9C\uDEA0-\uDED0\uDF00-\uDF1F\uDF2D-\uDF4A\uDF50-\uDF75\uDF80-\uDF9D\uDFA0-\uDFC3\uDFC8-\uDFCF\uDFD1-\uDFD5]|\uD801[\uDC00-\uDC9D\uDCB0-\uDCD3\uDCD8-\uDCFB\uDD00-\uDD27\uDD30-\uDD63\uDE00-\uDF36\uDF40-\uDF55\uDF60-\uDF67]|\uD802[\uDC00-\uDC05\uDC08\uDC0A-\uDC35\uDC37\uDC38\uDC3C\uDC3F-\uDC55\uDC60-\uDC76\uDC80-\uDC9E\uDCE0-\uDCF2\uDCF4\uDCF5\uDD00-\uDD15\uDD20-\uDD39\uDD80-\uDDB7\uDDBE\uDDBF\uDE00\uDE10-\uDE13\uDE15-\uDE17\uDE19-\uDE33\uDE60-\uDE7C\uDE80-\uDE9C\uDEC0-\uDEC7\uDEC9-\uDEE4\uDF00-\uDF35\uDF40-\uDF55\uDF60-\uDF72\uDF80-\uDF91]|\uD803[\uDC00-\uDC48\uDC80-\uDCB2\uDCC0-\uDCF2]|\uD804[\uDC03-\uDC37\uDC83-\uDCAF\uDCD0-\uDCE8\uDD03-\uDD26\uDD50-\uDD72\uDD76\uDD83-\uDDB2\uDDC1-\uDDC4\uDDDA\uDDDC\uDE00-\uDE11\uDE13-\uDE2B\uDE80-\uDE86\uDE88\uDE8A-\uDE8D\uDE8F-\uDE9D\uDE9F-\uDEA8\uDEB0-\uDEDE\uDF05-\uDF0C\uDF0F\uDF10\uDF13-\uDF28\uDF2A-\uDF30\uDF32\uDF33\uDF35-\uDF39\uDF3D\uDF50\uDF5D-\uDF61]|\uD805[\uDC00-\uDC34\uDC47-\uDC4A\uDC80-\uDCAF\uDCC4\uDCC5\uDCC7\uDD80-\uDDAE\uDDD8-\uDDDB\uDE00-\uDE2F\uDE44\uDE80-\uDEAA\uDF00-\uDF19]|\uD806[\uDCA0-\uDCDF\uDCFF\uDE00\uDE0B-\uDE32\uDE3A\uDE50\uDE5C-\uDE83\uDE86-\uDE89\uDEC0-\uDEF8]|\uD807[\uDC00-\uDC08\uDC0A-\uDC2E\uDC40\uDC72-\uDC8F\uDD00-\uDD06\uDD08\uDD09\uDD0B-\uDD30\uDD46]|\uD808[\uDC00-\uDF99]|\uD809[\uDC00-\uDC6E\uDC80-\uDD43]|[\uD80C\uD81C-\uD820\uD840-\uD868\uD86A-\uD86C\uD86F-\uD872\uD874-\uD879][\uDC00-\uDFFF]|\uD80D[\uDC00-\uDC2E]|\uD811[\uDC00-\uDE46]|\uD81A[\uDC00-\uDE38\uDE40-\uDE5E\uDED0-\uDEED\uDF00-\uDF2F\uDF40-\uDF43\uDF63-\uDF77\uDF7D-\uDF8F]|\uD81B[\uDF00-\uDF44\uDF50\uDF93-\uDF9F\uDFE0\uDFE1]|\uD821[\uDC00-\uDFEC]|\uD822[\uDC00-\uDEF2]|\uD82C[\uDC00-\uDD1E\uDD70-\uDEFB]|\uD82F[\uDC00-\uDC6A\uDC70-\uDC7C\uDC80-\uDC88\uDC90-\uDC99]|\uD835[\uDC00-\uDC54\uDC56-\uDC9C\uDC9E\uDC9F\uDCA2\uDCA5\uDCA6\uDCA9-\uDCAC\uDCAE-\uDCB9\uDCBB\uDCBD-\uDCC3\uDCC5-\uDD05\uDD07-\uDD0A\uDD0D-\uDD14\uDD16-\uDD1C\uDD1E-\uDD39\uDD3B-\uDD3E\uDD40-\uDD44\uDD46\uDD4A-\uDD50\uDD52-\uDEA5\uDEA8-\uDEC0\uDEC2-\uDEDA\uDEDC-\uDEFA\uDEFC-\uDF14\uDF16-\uDF34\uDF36-\uDF4E\uDF50-\uDF6E\uDF70-\uDF88\uDF8A-\uDFA8\uDFAA-\uDFC2\uDFC4-\uDFCB]|\uD83A[\uDC00-\uDCC4\uDD00-\uDD43]|\uD83B[\uDE00-\uDE03\uDE05-\uDE1F\uDE21\uDE22\uDE24\uDE27\uDE29-\uDE32\uDE34-\uDE37\uDE39\uDE3B\uDE42\uDE47\uDE49\uDE4B\uDE4D-\uDE4F\uDE51\uDE52\uDE54\uDE57\uDE59\uDE5B\uDE5D\uDE5F\uDE61\uDE62\uDE64\uDE67-\uDE6A\uDE6C-\uDE72\uDE74-\uDE77\uDE79-\uDE7C\uDE7E\uDE80-\uDE89\uDE8B-\uDE9B\uDEA1-\uDEA3\uDEA5-\uDEA9\uDEAB-\uDEBB]|\uD869[\uDC00-\uDED6\uDF00-\uDFFF]|\uD86D[\uDC00-\uDF34\uDF40-\uDFFF]|\uD86E[\uDC00-\uDC1D\uDC20-\uDFFF]|\uD873[\uDC00-\uDEA1\uDEB0-\uDFFF]|\uD87A[\uDC00-\uDFE0]|\uD87E[\uDC00-\uDE1D]/,ID_Continue:/[\xAA\xB5\xBA\xC0-\xD6\xD8-\xF6\xF8-\u02C1\u02C6-\u02D1\u02E0-\u02E4\u02EC\u02EE\u0300-\u0374\u0376\u0377\u037A-\u037D\u037F\u0386\u0388-\u038A\u038C\u038E-\u03A1\u03A3-\u03F5\u03F7-\u0481\u0483-\u0487\u048A-\u052F\u0531-\u0556\u0559\u0561-\u0587\u0591-\u05BD\u05BF\u05C1\u05C2\u05C4\u05C5\u05C7\u05D0-\u05EA\u05F0-\u05F2\u0610-\u061A\u0620-\u0669\u066E-\u06D3\u06D5-\u06DC\u06DF-\u06E8\u06EA-\u06FC\u06FF\u0710-\u074A\u074D-\u07B1\u07C0-\u07F5\u07FA\u0800-\u082D\u0840-\u085B\u0860-\u086A\u08A0-\u08B4\u08B6-\u08BD\u08D4-\u08E1\u08E3-\u0963\u0966-\u096F\u0971-\u0983\u0985-\u098C\u098F\u0990\u0993-\u09A8\u09AA-\u09B0\u09B2\u09B6-\u09B9\u09BC-\u09C4\u09C7\u09C8\u09CB-\u09CE\u09D7\u09DC\u09DD\u09DF-\u09E3\u09E6-\u09F1\u09FC\u0A01-\u0A03\u0A05-\u0A0A\u0A0F\u0A10\u0A13-\u0A28\u0A2A-\u0A30\u0A32\u0A33\u0A35\u0A36\u0A38\u0A39\u0A3C\u0A3E-\u0A42\u0A47\u0A48\u0A4B-\u0A4D\u0A51\u0A59-\u0A5C\u0A5E\u0A66-\u0A75\u0A81-\u0A83\u0A85-\u0A8D\u0A8F-\u0A91\u0A93-\u0AA8\u0AAA-\u0AB0\u0AB2\u0AB3\u0AB5-\u0AB9\u0ABC-\u0AC5\u0AC7-\u0AC9\u0ACB-\u0ACD\u0AD0\u0AE0-\u0AE3\u0AE6-\u0AEF\u0AF9-\u0AFF\u0B01-\u0B03\u0B05-\u0B0C\u0B0F\u0B10\u0B13-\u0B28\u0B2A-\u0B30\u0B32\u0B33\u0B35-\u0B39\u0B3C-\u0B44\u0B47\u0B48\u0B4B-\u0B4D\u0B56\u0B57\u0B5C\u0B5D\u0B5F-\u0B63\u0B66-\u0B6F\u0B71\u0B82\u0B83\u0B85-\u0B8A\u0B8E-\u0B90\u0B92-\u0B95\u0B99\u0B9A\u0B9C\u0B9E\u0B9F\u0BA3\u0BA4\u0BA8-\u0BAA\u0BAE-\u0BB9\u0BBE-\u0BC2\u0BC6-\u0BC8\u0BCA-\u0BCD\u0BD0\u0BD7\u0BE6-\u0BEF\u0C00-\u0C03\u0C05-\u0C0C\u0C0E-\u0C10\u0C12-\u0C28\u0C2A-\u0C39\u0C3D-\u0C44\u0C46-\u0C48\u0C4A-\u0C4D\u0C55\u0C56\u0C58-\u0C5A\u0C60-\u0C63\u0C66-\u0C6F\u0C80-\u0C83\u0C85-\u0C8C\u0C8E-\u0C90\u0C92-\u0CA8\u0CAA-\u0CB3\u0CB5-\u0CB9\u0CBC-\u0CC4\u0CC6-\u0CC8\u0CCA-\u0CCD\u0CD5\u0CD6\u0CDE\u0CE0-\u0CE3\u0CE6-\u0CEF\u0CF1\u0CF2\u0D00-\u0D03\u0D05-\u0D0C\u0D0E-\u0D10\u0D12-\u0D44\u0D46-\u0D48\u0D4A-\u0D4E\u0D54-\u0D57\u0D5F-\u0D63\u0D66-\u0D6F\u0D7A-\u0D7F\u0D82\u0D83\u0D85-\u0D96\u0D9A-\u0DB1\u0DB3-\u0DBB\u0DBD\u0DC0-\u0DC6\u0DCA\u0DCF-\u0DD4\u0DD6\u0DD8-\u0DDF\u0DE6-\u0DEF\u0DF2\u0DF3\u0E01-\u0E3A\u0E40-\u0E4E\u0E50-\u0E59\u0E81\u0E82\u0E84\u0E87\u0E88\u0E8A\u0E8D\u0E94-\u0E97\u0E99-\u0E9F\u0EA1-\u0EA3\u0EA5\u0EA7\u0EAA\u0EAB\u0EAD-\u0EB9\u0EBB-\u0EBD\u0EC0-\u0EC4\u0EC6\u0EC8-\u0ECD\u0ED0-\u0ED9\u0EDC-\u0EDF\u0F00\u0F18\u0F19\u0F20-\u0F29\u0F35\u0F37\u0F39\u0F3E-\u0F47\u0F49-\u0F6C\u0F71-\u0F84\u0F86-\u0F97\u0F99-\u0FBC\u0FC6\u1000-\u1049\u1050-\u109D\u10A0-\u10C5\u10C7\u10CD\u10D0-\u10FA\u10FC-\u1248\u124A-\u124D\u1250-\u1256\u1258\u125A-\u125D\u1260-\u1288\u128A-\u128D\u1290-\u12B0\u12B2-\u12B5\u12B8-\u12BE\u12C0\u12C2-\u12C5\u12C8-\u12D6\u12D8-\u1310\u1312-\u1315\u1318-\u135A\u135D-\u135F\u1380-\u138F\u13A0-\u13F5\u13F8-\u13FD\u1401-\u166C\u166F-\u167F\u1681-\u169A\u16A0-\u16EA\u16EE-\u16F8\u1700-\u170C\u170E-\u1714\u1720-\u1734\u1740-\u1753\u1760-\u176C\u176E-\u1770\u1772\u1773\u1780-\u17D3\u17D7\u17DC\u17DD\u17E0-\u17E9\u180B-\u180D\u1810-\u1819\u1820-\u1877\u1880-\u18AA\u18B0-\u18F5\u1900-\u191E\u1920-\u192B\u1930-\u193B\u1946-\u196D\u1970-\u1974\u1980-\u19AB\u19B0-\u19C9\u19D0-\u19D9\u1A00-\u1A1B\u1A20-\u1A5E\u1A60-\u1A7C\u1A7F-\u1A89\u1A90-\u1A99\u1AA7\u1AB0-\u1ABD\u1B00-\u1B4B\u1B50-\u1B59\u1B6B-\u1B73\u1B80-\u1BF3\u1C00-\u1C37\u1C40-\u1C49\u1C4D-\u1C7D\u1C80-\u1C88\u1CD0-\u1CD2\u1CD4-\u1CF9\u1D00-\u1DF9\u1DFB-\u1F15\u1F18-\u1F1D\u1F20-\u1F45\u1F48-\u1F4D\u1F50-\u1F57\u1F59\u1F5B\u1F5D\u1F5F-\u1F7D\u1F80-\u1FB4\u1FB6-\u1FBC\u1FBE\u1FC2-\u1FC4\u1FC6-\u1FCC\u1FD0-\u1FD3\u1FD6-\u1FDB\u1FE0-\u1FEC\u1FF2-\u1FF4\u1FF6-\u1FFC\u203F\u2040\u2054\u2071\u207F\u2090-\u209C\u20D0-\u20DC\u20E1\u20E5-\u20F0\u2102\u2107\u210A-\u2113\u2115\u2119-\u211D\u2124\u2126\u2128\u212A-\u212D\u212F-\u2139\u213C-\u213F\u2145-\u2149\u214E\u2160-\u2188\u2C00-\u2C2E\u2C30-\u2C5E\u2C60-\u2CE4\u2CEB-\u2CF3\u2D00-\u2D25\u2D27\u2D2D\u2D30-\u2D67\u2D6F\u2D7F-\u2D96\u2DA0-\u2DA6\u2DA8-\u2DAE\u2DB0-\u2DB6\u2DB8-\u2DBE\u2DC0-\u2DC6\u2DC8-\u2DCE\u2DD0-\u2DD6\u2DD8-\u2DDE\u2DE0-\u2DFF\u2E2F\u3005-\u3007\u3021-\u302F\u3031-\u3035\u3038-\u303C\u3041-\u3096\u3099\u309A\u309D-\u309F\u30A1-\u30FA\u30FC-\u30FF\u3105-\u312E\u3131-\u318E\u31A0-\u31BA\u31F0-\u31FF\u3400-\u4DB5\u4E00-\u9FEA\uA000-\uA48C\uA4D0-\uA4FD\uA500-\uA60C\uA610-\uA62B\uA640-\uA66F\uA674-\uA67D\uA67F-\uA6F1\uA717-\uA71F\uA722-\uA788\uA78B-\uA7AE\uA7B0-\uA7B7\uA7F7-\uA827\uA840-\uA873\uA880-\uA8C5\uA8D0-\uA8D9\uA8E0-\uA8F7\uA8FB\uA8FD\uA900-\uA92D\uA930-\uA953\uA960-\uA97C\uA980-\uA9C0\uA9CF-\uA9D9\uA9E0-\uA9FE\uAA00-\uAA36\uAA40-\uAA4D\uAA50-\uAA59\uAA60-\uAA76\uAA7A-\uAAC2\uAADB-\uAADD\uAAE0-\uAAEF\uAAF2-\uAAF6\uAB01-\uAB06\uAB09-\uAB0E\uAB11-\uAB16\uAB20-\uAB26\uAB28-\uAB2E\uAB30-\uAB5A\uAB5C-\uAB65\uAB70-\uABEA\uABEC\uABED\uABF0-\uABF9\uAC00-\uD7A3\uD7B0-\uD7C6\uD7CB-\uD7FB\uF900-\uFA6D\uFA70-\uFAD9\uFB00-\uFB06\uFB13-\uFB17\uFB1D-\uFB28\uFB2A-\uFB36\uFB38-\uFB3C\uFB3E\uFB40\uFB41\uFB43\uFB44\uFB46-\uFBB1\uFBD3-\uFD3D\uFD50-\uFD8F\uFD92-\uFDC7\uFDF0-\uFDFB\uFE00-\uFE0F\uFE20-\uFE2F\uFE33\uFE34\uFE4D-\uFE4F\uFE70-\uFE74\uFE76-\uFEFC\uFF10-\uFF19\uFF21-\uFF3A\uFF3F\uFF41-\uFF5A\uFF66-\uFFBE\uFFC2-\uFFC7\uFFCA-\uFFCF\uFFD2-\uFFD7\uFFDA-\uFFDC]|\uD800[\uDC00-\uDC0B\uDC0D-\uDC26\uDC28-\uDC3A\uDC3C\uDC3D\uDC3F-\uDC4D\uDC50-\uDC5D\uDC80-\uDCFA\uDD40-\uDD74\uDDFD\uDE80-\uDE9C\uDEA0-\uDED0\uDEE0\uDF00-\uDF1F\uDF2D-\uDF4A\uDF50-\uDF7A\uDF80-\uDF9D\uDFA0-\uDFC3\uDFC8-\uDFCF\uDFD1-\uDFD5]|\uD801[\uDC00-\uDC9D\uDCA0-\uDCA9\uDCB0-\uDCD3\uDCD8-\uDCFB\uDD00-\uDD27\uDD30-\uDD63\uDE00-\uDF36\uDF40-\uDF55\uDF60-\uDF67]|\uD802[\uDC00-\uDC05\uDC08\uDC0A-\uDC35\uDC37\uDC38\uDC3C\uDC3F-\uDC55\uDC60-\uDC76\uDC80-\uDC9E\uDCE0-\uDCF2\uDCF4\uDCF5\uDD00-\uDD15\uDD20-\uDD39\uDD80-\uDDB7\uDDBE\uDDBF\uDE00-\uDE03\uDE05\uDE06\uDE0C-\uDE13\uDE15-\uDE17\uDE19-\uDE33\uDE38-\uDE3A\uDE3F\uDE60-\uDE7C\uDE80-\uDE9C\uDEC0-\uDEC7\uDEC9-\uDEE6\uDF00-\uDF35\uDF40-\uDF55\uDF60-\uDF72\uDF80-\uDF91]|\uD803[\uDC00-\uDC48\uDC80-\uDCB2\uDCC0-\uDCF2]|\uD804[\uDC00-\uDC46\uDC66-\uDC6F\uDC7F-\uDCBA\uDCD0-\uDCE8\uDCF0-\uDCF9\uDD00-\uDD34\uDD36-\uDD3F\uDD50-\uDD73\uDD76\uDD80-\uDDC4\uDDCA-\uDDCC\uDDD0-\uDDDA\uDDDC\uDE00-\uDE11\uDE13-\uDE37\uDE3E\uDE80-\uDE86\uDE88\uDE8A-\uDE8D\uDE8F-\uDE9D\uDE9F-\uDEA8\uDEB0-\uDEEA\uDEF0-\uDEF9\uDF00-\uDF03\uDF05-\uDF0C\uDF0F\uDF10\uDF13-\uDF28\uDF2A-\uDF30\uDF32\uDF33\uDF35-\uDF39\uDF3C-\uDF44\uDF47\uDF48\uDF4B-\uDF4D\uDF50\uDF57\uDF5D-\uDF63\uDF66-\uDF6C\uDF70-\uDF74]|\uD805[\uDC00-\uDC4A\uDC50-\uDC59\uDC80-\uDCC5\uDCC7\uDCD0-\uDCD9\uDD80-\uDDB5\uDDB8-\uDDC0\uDDD8-\uDDDD\uDE00-\uDE40\uDE44\uDE50-\uDE59\uDE80-\uDEB7\uDEC0-\uDEC9\uDF00-\uDF19\uDF1D-\uDF2B\uDF30-\uDF39]|\uD806[\uDCA0-\uDCE9\uDCFF\uDE00-\uDE3E\uDE47\uDE50-\uDE83\uDE86-\uDE99\uDEC0-\uDEF8]|\uD807[\uDC00-\uDC08\uDC0A-\uDC36\uDC38-\uDC40\uDC50-\uDC59\uDC72-\uDC8F\uDC92-\uDCA7\uDCA9-\uDCB6\uDD00-\uDD06\uDD08\uDD09\uDD0B-\uDD36\uDD3A\uDD3C\uDD3D\uDD3F-\uDD47\uDD50-\uDD59]|\uD808[\uDC00-\uDF99]|\uD809[\uDC00-\uDC6E\uDC80-\uDD43]|[\uD80C\uD81C-\uD820\uD840-\uD868\uD86A-\uD86C\uD86F-\uD872\uD874-\uD879][\uDC00-\uDFFF]|\uD80D[\uDC00-\uDC2E]|\uD811[\uDC00-\uDE46]|\uD81A[\uDC00-\uDE38\uDE40-\uDE5E\uDE60-\uDE69\uDED0-\uDEED\uDEF0-\uDEF4\uDF00-\uDF36\uDF40-\uDF43\uDF50-\uDF59\uDF63-\uDF77\uDF7D-\uDF8F]|\uD81B[\uDF00-\uDF44\uDF50-\uDF7E\uDF8F-\uDF9F\uDFE0\uDFE1]|\uD821[\uDC00-\uDFEC]|\uD822[\uDC00-\uDEF2]|\uD82C[\uDC00-\uDD1E\uDD70-\uDEFB]|\uD82F[\uDC00-\uDC6A\uDC70-\uDC7C\uDC80-\uDC88\uDC90-\uDC99\uDC9D\uDC9E]|\uD834[\uDD65-\uDD69\uDD6D-\uDD72\uDD7B-\uDD82\uDD85-\uDD8B\uDDAA-\uDDAD\uDE42-\uDE44]|\uD835[\uDC00-\uDC54\uDC56-\uDC9C\uDC9E\uDC9F\uDCA2\uDCA5\uDCA6\uDCA9-\uDCAC\uDCAE-\uDCB9\uDCBB\uDCBD-\uDCC3\uDCC5-\uDD05\uDD07-\uDD0A\uDD0D-\uDD14\uDD16-\uDD1C\uDD1E-\uDD39\uDD3B-\uDD3E\uDD40-\uDD44\uDD46\uDD4A-\uDD50\uDD52-\uDEA5\uDEA8-\uDEC0\uDEC2-\uDEDA\uDEDC-\uDEFA\uDEFC-\uDF14\uDF16-\uDF34\uDF36-\uDF4E\uDF50-\uDF6E\uDF70-\uDF88\uDF8A-\uDFA8\uDFAA-\uDFC2\uDFC4-\uDFCB\uDFCE-\uDFFF]|\uD836[\uDE00-\uDE36\uDE3B-\uDE6C\uDE75\uDE84\uDE9B-\uDE9F\uDEA1-\uDEAF]|\uD838[\uDC00-\uDC06\uDC08-\uDC18\uDC1B-\uDC21\uDC23\uDC24\uDC26-\uDC2A]|\uD83A[\uDC00-\uDCC4\uDCD0-\uDCD6\uDD00-\uDD4A\uDD50-\uDD59]|\uD83B[\uDE00-\uDE03\uDE05-\uDE1F\uDE21\uDE22\uDE24\uDE27\uDE29-\uDE32\uDE34-\uDE37\uDE39\uDE3B\uDE42\uDE47\uDE49\uDE4B\uDE4D-\uDE4F\uDE51\uDE52\uDE54\uDE57\uDE59\uDE5B\uDE5D\uDE5F\uDE61\uDE62\uDE64\uDE67-\uDE6A\uDE6C-\uDE72\uDE74-\uDE77\uDE79-\uDE7C\uDE7E\uDE80-\uDE89\uDE8B-\uDE9B\uDEA1-\uDEA3\uDEA5-\uDEA9\uDEAB-\uDEBB]|\uD869[\uDC00-\uDED6\uDF00-\uDFFF]|\uD86D[\uDC00-\uDF34\uDF40-\uDFFF]|\uD86E[\uDC00-\uDC1D\uDC20-\uDFFF]|\uD873[\uDC00-\uDEA1\uDEB0-\uDFFF]|\uD87A[\uDC00-\uDFE0]|\uD87E[\uDC00-\uDE1D]|\uDB40[\uDD00-\uDDEF]/},ne={isSpaceSeparator:function(e){return"string"==typeof e&&te.Space_Separator.test(e)},isIdStartChar:function(e){return"string"==typeof e&&(e>="a"&&e<="z"||e>="A"&&e<="Z"||"$"===e||"_"===e||te.ID_Start.test(e))},isIdContinueChar:function(e){return"string"==typeof e&&(e>="a"&&e<="z"||e>="A"&&e<="Z"||e>="0"&&e<="9"||"$"===e||"_"===e||"‌"===e||"‍"===e||te.ID_Continue.test(e))},isDigit:function(e){return"string"==typeof e&&/[0-9]/.test(e)},isHexDigit:function(e){return"string"==typeof e&&/[0-9A-Fa-f]/.test(e)}},re=function(e,t){R=String(e),U="start",z=[],q=0,V=1,H=0,G=void 0,K=void 0,W=void 0;do{G=ie(),pe[U]()}while("eof"!==G.type);return"function"==typeof t?ue({"":W},"",t):W};function ue(e,t,n){var r=e[t];if(null!=r&&"object"==typeof r)if(Array.isArray(r))for(var u=0;u<r.length;u++){var i=String(u),o=ue(r,i,n);void 0===o?delete r[i]:Object.defineProperty(r,i,{value:o,writable:!0,enumerable:!0,configurable:!0})}else for(var s in r){var a=ue(r,s,n);void 0===a?delete r[s]:Object.defineProperty(r,s,{value:a,writable:!0,enumerable:!0,configurable:!0})}return n.call(e,t,r)}function ie(){for(Q="default",J="",X=!1,Y=1;;){ee=oe();var e=ae[Q]();if(e)return e}}function oe(){if(R[q])return String.fromCodePoint(R.codePointAt(q))}function se(){var e=oe();return"\n"===e?(V++,H=0):e?H+=e.length:H++,e&&(q+=e.length),e}var ae={default:function(){switch(ee){case"\t":case"\v":case"\f":case" ":case" ":case"\ufeff":case"\n":case"\r":case"\u2028":case"\u2029":return void se();case"/":return se(),void(Q="comment");case void 0:return se(),ce("eof")}if(!ne.isSpaceSeparator(ee))return ae[U]();se()},comment:function(){switch(ee){case"*":return se(),void(Q="multiLineComment");case"/":return se(),void(Q="singleLineComment")}throw me(se())},multiLineComment:function(){switch(ee){case"*":return se(),void(Q="multiLineCommentAsterisk");case void 0:throw me(se())}se()},multiLineCommentAsterisk:function(){switch(ee){case"*":return void se();case"/":return se(),void(Q="default");case void 0:throw me(se())}se(),Q="multiLineComment"},singleLineComment:function(){switch(ee){case"\n":case"\r":case"\u2028":case"\u2029":return se(),void(Q="default");case void 0:return se(),ce("eof")}se()},value:function(){switch(ee){case"{":case"[":return ce("punctuator",se());case"n":return se(),le("ull"),ce("null",null);case"t":return se(),le("rue"),ce("boolean",!0);case"f":return se(),le("alse"),ce("boolean",!1);case"-":case"+":return"-"===se()&&(Y=-1),void(Q="sign");case".":return J=se(),void(Q="decimalPointLeading");case"0":return J=se(),void(Q="zero");case"1":case"2":case"3":case"4":case"5":case"6":case"7":case"8":case"9":return J=se(),void(Q="decimalInteger");case"I":return se(),le("nfinity"),ce("numeric",1/0);case"N":return se(),le("aN"),ce("numeric",NaN);case'"':case"'":return X='"'===se(),J="",void(Q="string")}throw me(se())},identifierNameStartEscape:function(){if("u"!==ee)throw me(se());se();var e=De();switch(e){case"$":case"_":break;default:if(!ne.isIdStartChar(e))throw Ce()}J+=e,Q="identifierName"},identifierName:function(){switch(ee){case"$":case"_":case"‌":case"‍":return void(J+=se());case"\\":return se(),void(Q="identifierNameEscape")}if(!ne.isIdContinueChar(ee))return ce("identifier",J);J+=se()},identifierNameEscape:function(){if("u"!==ee)throw me(se());se();var e=De();switch(e){case"$":case"_":case"‌":case"‍":break;default:if(!ne.isIdContinueChar(e))throw Ce()}J+=e,Q="identifierName"},sign:function(){switch(ee){case".":return J=se(),void(Q="decimalPointLeading");case"0":return J=se(),void(Q="zero");case"1":case"2":case"3":case"4":case"5":case"6":case"7":case"8":case"9":return J=se(),void(Q="decimalInteger");case"I":return se(),le("nfinity"),ce("numeric",Y*(1/0));case"N":return se(),le("aN"),ce("numeric",NaN)}throw me(se())},zero:function(){switch(ee){case".":return J+=se(),void(Q="decimalPoint");case"e":case"E":return J+=se(),void(Q="decimalExponent");case"x":case"X":return J+=se(),void(Q="hexadecimal")}return ce("numeric",0*Y)},decimalInteger:function(){switch(ee){case".":return J+=se(),void(Q="decimalPoint");case"e":case"E":return J+=se(),void(Q="decimalExponent")}if(!ne.isDigit(ee))return ce("numeric",Y*Number(J));J+=se()},decimalPointLeading:function(){if(ne.isDigit(ee))return J+=se(),void(Q="decimalFraction");throw me(se())},decimalPoint:function(){switch(ee){case"e":case"E":return J+=se(),void(Q="decimalExponent")}return ne.isDigit(ee)?(J+=se(),void(Q="decimalFraction")):ce("numeric",Y*Number(J))},decimalFraction:function(){switch(ee){case"e":case"E":return J+=se(),void(Q="decimalExponent")}if(!ne.isDigit(ee))return ce("numeric",Y*Number(J));J+=se()},decimalExponent:function(){switch(ee){case"+":case"-":return J+=se(),void(Q="decimalExponentSign")}if(ne.isDigit(ee))return J+=se(),void(Q="decimalExponentInteger");throw me(se())},decimalExponentSign:function(){if(ne.isDigit(ee))return J+=se(),void(Q="decimalExponentInteger");throw me(se())},decimalExponentInteger:function(){if(!ne.isDigit(ee))return ce("numeric",Y*Number(J));J+=se()},hexadecimal:function(){if(ne.isHexDigit(ee))return J+=se(),void(Q="hexadecimalInteger");throw me(se())},hexadecimalInteger:function(){if(!ne.isHexDigit(ee))return ce("numeric",Y*Number(J));J+=se()},string:function(){switch(ee){case"\\":return se(),void(J+=de());case'"':return X?(se(),ce("string",J)):void(J+=se());case"'":return X?void(J+=se()):(se(),ce("string",J));case"\n":case"\r":throw me(se());case"\u2028":case"\u2029":Fe(ee);break;case void 0:throw me(se())}J+=se()},start:function(){switch(ee){case"{":case"[":return ce("punctuator",se())}Q="value"},beforePropertyName:function(){switch(ee){case"$":case"_":return J=se(),void(Q="identifierName");case"\\":return se(),void(Q="identifierNameStartEscape");case"}":return ce("punctuator",se());case'"':case"'":return X='"'===se(),void(Q="string")}if(ne.isIdStartChar(ee))return J+=se(),void(Q="identifierName");throw me(se())},afterPropertyName:function(){if(":"===ee)return ce("punctuator",se());throw me(se())},beforePropertyValue:function(){Q="value"},afterPropertyValue:function(){switch(ee){case",":case"}":return ce("punctuator",se())}throw me(se())},beforeArrayValue:function(){if("]"===ee)return ce("punctuator",se());Q="value"},afterArrayValue:function(){switch(ee){case",":case"]":return ce("punctuator",se())}throw me(se())},end:function(){throw me(se())}};function ce(e,t){return{type:e,value:t,line:V,column:H}}function le(e){for(var t=0,n=e;t<n.length;t+=1){var r=n[t];if(oe()!==r)throw me(se());se()}}function de(){switch(oe()){case"b":return se(),"\b";case"f":return se(),"\f";case"n":return se(),"\n";case"r":return se(),"\r";case"t":return se(),"\t";case"v":return se(),"\v";case"0":if(se(),ne.isDigit(oe()))throw me(se());return"\0";case"x":return se(),fe();case"u":return se(),De();case"\n":case"\u2028":case"\u2029":return se(),"";case"\r":return se(),"\n"===oe()&&se(),"";case"1":case"2":case"3":case"4":case"5":case"6":case"7":case"8":case"9":case void 0:throw me(se())}return se()}function fe(){var e="",t=oe();if(!ne.isHexDigit(t))throw me(se());if(e+=se(),t=oe(),!ne.isHexDigit(t))throw me(se());return e+=se(),String.fromCodePoint(parseInt(e,16))}function De(){for(var e="",t=4;t-- >0;){var n=oe();if(!ne.isHexDigit(n))throw me(se());e+=se()}return String.fromCodePoint(parseInt(e,16))}var pe={start:function(){if("eof"===G.type)throw ye();he()},beforePropertyName:function(){switch(G.type){case"identifier":case"string":return K=G.value,void(U="afterPropertyName");case"punctuator":return void ge();case"eof":throw ye()}},afterPropertyName:function(){if("eof"===G.type)throw ye();U="beforePropertyValue"},beforePropertyValue:function(){if("eof"===G.type)throw ye();he()},beforeArrayValue:function(){if("eof"===G.type)throw ye();"punctuator"!==G.type||"]"!==G.value?he():ge()},afterPropertyValue:function(){if("eof"===G.type)throw ye();switch(G.value){case",":return void(U="beforePropertyName");case"}":ge()}},afterArrayValue:function(){if("eof"===G.type)throw ye();switch(G.value){case",":return void(U="beforeArrayValue");case"]":ge()}},end:function(){}};function he(){var e;switch(G.type){case"punctuator":switch(G.value){case"{":e={};break;case"[":e=[]}break;case"null":case"boolean":case"numeric":case"string":e=G.value}if(void 0===W)W=e;else{var t=z[z.length-1];Array.isArray(t)?t.push(e):Object.defineProperty(t,K,{value:e,writable:!0,enumerable:!0,configurable:!0})}if(null!==e&&"object"==typeof e)z.push(e),U=Array.isArray(e)?"beforeArrayValue":"beforePropertyName";else{var n=z[z.length-1];U=null==n?"end":Array.isArray(n)?"afterArrayValue":"afterPropertyValue"}}function ge(){z.pop();var e=z[z.length-1];U=null==e?"end":Array.isArray(e)?"afterArrayValue":"afterPropertyValue"}function me(e){return Ae(void 0===e?"JSON5: invalid end of input at "+V+":"+H:"JSON5: invalid character '"+ve(e)+"' at "+V+":"+H)}function ye(){return Ae("JSON5: invalid end of input at "+V+":"+H)}function Ce(){return Ae("JSON5: invalid identifier character at "+V+":"+(H-=5))}function Fe(e){console.warn("JSON5: '"+ve(e)+"' in strings is not valid ECMAScript; consider escaping")}function ve(e){var t={"'":"\\'",'"':'\\"',"\\":"\\\\","\b":"\\b","\f":"\\f","\n":"\\n","\r":"\\r","\t":"\\t","\v":"\\v","\0":"\\0","\u2028":"\\u2028","\u2029":"\\u2029"};if(t[e])return t[e];if(e<" "){var n=e.charCodeAt(0).toString(16);return"\\x"+("00"+n).substring(n.length)}return e}function Ae(e){var t=new SyntaxError(e);return t.lineNumber=V,t.columnNumber=H,t}return{parse:re,stringify:function(e,t,n){var r,u,i,o=[],s="",a="";if(null==t||"object"!=typeof t||Array.isArray(t)||(n=t.space,i=t.quote,t=t.replacer),"function"==typeof t)u=t;else if(Array.isArray(t)){r=[];for(var c=0,l=t;c<l.length;c+=1){var d=l[c],f=void 0;"string"==typeof d?f=d:("number"==typeof d||d instanceof String||d instanceof Number)&&(f=String(d)),void 0!==f&&r.indexOf(f)<0&&r.push(f)}}return n instanceof Number?n=Number(n):n instanceof String&&(n=String(n)),"number"==typeof n?n>0&&(n=Math.min(10,Math.floor(n)),a="          ".substr(0,n)):"string"==typeof n&&(a=n.substr(0,10)),D("",{"":e});function D(e,t){var n=t[e];switch(null!=n&&("function"==typeof n.toJSON5?n=n.toJSON5(e):"function"==typeof n.toJSON&&(n=n.toJSON(e))),u&&(n=u.call(t,e,n)),n instanceof Number?n=Number(n):n instanceof String?n=String(n):n instanceof Boolean&&(n=n.valueOf()),n){case null:return"null";case!0:return"true";case!1:return"false"}return"string"==typeof n?p(n,!1):"number"==typeof n?String(n):"object"==typeof n?Array.isArray(n)?m(n):h(n):void 0}function p(e){for(var t={"'":.1,'"':.2},n={"'":"\\'",'"':'\\"',"\\":"\\\\","\b":"\\b","\f":"\\f","\n":"\\n","\r":"\\r","\t":"\\t","\v":"\\v","\0":"\\0","\u2028":"\\u2028","\u2029":"\\u2029"},r="",u=0;u<e.length;u++){var o=e[u];switch(o){case"'":case'"':t[o]++,r+=o;continue;case"\0":if(ne.isDigit(e[u+1])){r+="\\x00";continue}}if(n[o])r+=n[o];else if(o<" "){var s=o.charCodeAt(0).toString(16);r+="\\x"+("00"+s).substring(s.length)}else r+=o}var a=i||Object.keys(t).reduce((function(e,n){return t[e]<t[n]?e:n}));return a+(r=r.replace(new RegExp(a,"g"),n[a]))+a}function h(e){if(o.indexOf(e)>=0)throw TypeError("Converting circular structure to JSON5");o.push(e);var t=s;s+=a;for(var n,u,i=[],c=0,l=r||Object.keys(e);c<l.length;c+=1){var d=l[c],f=D(d,e);if(void 0!==f){var p=g(d)+":";""!==a&&(p+=" "),p+=f,i.push(p)}}if(0===i.length)n="{}";else if(""===a)n="{"+(u=i.join(","))+"}";else{var h=",\n"+s;u=i.join(h),n="{\n"+s+u+",\n"+t+"}"}return o.pop(),s=t,n}function g(e){if(0===e.length)return p(e,!0);var t=String.fromCodePoint(e.codePointAt(0));if(!ne.isIdStartChar(t))return p(e,!0);for(var n=t.length;n<e.length;n++)if(!ne.isIdContinueChar(String.fromCodePoint(e.codePointAt(n))))return p(e,!0);return e}function m(e){if(o.indexOf(e)>=0)throw TypeError("Converting circular structure to JSON5");o.push(e);var t=s;s+=a;for(var n,r=[],u=0;u<e.length;u++){var i=D(String(u),e);r.push(void 0!==i?i:"null")}if(0===r.length)n="[]";else if(""===a)n="["+r.join(",")+"]";else{var c=",\n"+s,l=r.join(c);n="[\n"+s+l+",\n"+t+"]"}return o.pop(),s=t,n}}}}()},1096:function(e){e.exports=function(){"use strict";function e(){}function t(e){if(!(this instanceof t))throw new TypeError("Promises must be constructed via new");if("function"!=typeof e)throw new TypeError("not a function");this._state=0,this._handled=!1,this._value=void 0,this._deferreds=[],o(e,this)}function n(e,n){for(;3===e._state;)e=e._value;0!==e._state?(e._handled=!0,t._immediateFn((function(){var t=1===e._state?n.onFulfilled:n.onRejected;if(null!==t){var i;try{i=t(e._value)}catch(e){return void u(n.promise,e)}r(n.promise,i)}else(1===e._state?r:u)(n.promise,e._value)}))):e._deferreds.push(n)}function r(e,n){try{if(n===e)throw new TypeError("A promise cannot be resolved with itself.");if(n&&("object"==typeof n||"function"==typeof n)){var r=n.then;if(n instanceof t)return e._state=3,e._value=n,void i(e);if("function"==typeof r)return void o(function(e,t){return function(){e.apply(t,arguments)}}(r,n),e)}e._state=1,e._value=n,i(e)}catch(t){u(e,t)}}function u(e,t){e._state=2,e._value=t,i(e)}function i(e){2===e._state&&0===e._deferreds.length&&t._immediateFn((function(){e._handled||t._unhandledRejectionFn(e._value)}));for(var r=0,u=e._deferreds.length;u>r;r++)n(e,e._deferreds[r]);e._deferreds=null}function o(e,t){var n=!1;try{e((function(e){n||(n=!0,r(t,e))}),(function(e){n||(n=!0,u(t,e))}))}catch(e){if(n)return;n=!0,u(t,e)}}var s=setTimeout;return t.prototype.catch=function(e){return this.then(null,e)},t.prototype.then=function(t,r){var u=new this.constructor(e);return n(this,new function(e,t,n){this.onFulfilled="function"==typeof e?e:null,this.onRejected="function"==typeof t?t:null,this.promise=n}(t,r,u)),u},t.prototype.finally=function(e){var t=this.constructor;return this.then((function(n){return t.resolve(e()).then((function(){return n}))}),(function(n){return t.resolve(e()).then((function(){return t.reject(n)}))}))},t.all=function(e){return new t((function(t,n){function r(e,o){try{if(o&&("object"==typeof o||"function"==typeof o)){var s=o.then;if("function"==typeof s)return void s.call(o,(function(t){r(e,t)}),n)}u[e]=o,0==--i&&t(u)}catch(e){n(e)}}if(!e||void 0===e.length)throw new TypeError("Promise.all accepts an array");var u=Array.prototype.slice.call(e);if(0===u.length)return t([]);for(var i=u.length,o=0;u.length>o;o++)r(o,u[o])}))},t.resolve=function(e){return e&&"object"==typeof e&&e.constructor===t?e:new t((function(t){t(e)}))},t.reject=function(e){return new t((function(t,n){n(e)}))},t.race=function(e){return new t((function(t,n){for(var r=0,u=e.length;u>r;r++)e[r].then(t,n)}))},t._immediateFn="function"==typeof setImmediate&&function(e){setImmediate(e)}||function(e){s(e,0)},t._unhandledRejectionFn=function(e){void 0!==console&&console&&console.warn("Possible Unhandled Promise Rejection:",e)},t}()},9563:e=>{var t,n,r={},u={},i=(t=function(){return document.head||document.getElementsByTagName("head")[0]},function(){return void 0===n&&(n=t.apply(this,arguments)),n});function o(e){var t=document.createElement("style");return t.type="text/css",t.setAttribute("data-jwplayer-id",e),function(e){i().appendChild(e)}(t),t}function s(e,t){var n,r,i,s=u[e];s||(s=u[e]={element:o(e),counter:0});var a=s.counter++;return n=s.element,i=function(){l(n,a,"")},(r=function(e){l(n,a,e)})(t.css),function(e){if(e){if(e.css===t.css&&e.media===t.media)return;r((t=e).css)}else i()}}e.exports={style:function(e,t){!function(e,t){for(var n=0;n<t.length;n++){var u=t[n],i=(r[e]||{})[u.id];if(i){for(var o=0;o<i.parts.length;o++)i.parts[o](u.parts[o]);for(;o<u.parts.length;o++)i.parts.push(s(e,u.parts[o]))}else{var a=[];for(o=0;o<u.parts.length;o++)a.push(s(e,u.parts[o]));r[e]=r[e]||{},r[e][u.id]={id:u.id,parts:a}}}}(t,function(e){for(var t=[],n={},r=0;r<e.length;r++){var u=e[r],i=u[0],o={css:u[1],media:u[2]};n[i]?n[i].parts.push(o):t.push(n[i]={id:i,parts:[o]})}return t}(e))},clear:function(e,t){var n=r[e];if(!n)return;if(t){var u=n[t];if(u)for(var i=0;i<u.parts.length;i+=1)u.parts[i]();return}for(var o=Object.keys(n),s=0;s<o.length;s+=1)for(var a=n[o[s]],c=0;c<a.parts.length;c+=1)a.parts[c]();delete r[e]}};var a,c=(a=[],function(e,t){return a[e]=t,a.filter(Boolean).join("\n")});function l(e,t,n){if(e.styleSheet)e.styleSheet.cssText=c(t,n);else{var r=document.createTextNode(n),u=e.childNodes[t];u?e.replaceChild(r,u):e.appendChild(r)}}},4737:e=>{e.exports='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 29.3" class="jw-svg-icon jw-svg-icon-watermark" focusable="false"><path d="M37,16.68c0,2.4-.59,3.43-2.4,3.43a5.75,5.75,0,0,1-3.38-1.23v3.58a7.39,7.39,0,0,0,3.67,1c3.67,0,5.73-1.91,5.73-6.32V5.86H37Z"></path><polygon points="58.33 17.61 55.39 6.01 52.55 6.01 49.52 17.61 46.73 6.01 43.06 6.01 47.56 23.29 50.89 23.29 53.92 11.88 56.96 23.29 60.24 23.29 64.74 6.01 61.17 6.01 58.33 17.61"></polygon><path d="M73.84,6H67.47V23.29h2.2v-6.9h4.17c3.47,0,5.77-1.77,5.77-5.19S77.31,6,73.84,6Zm0,8.47H69.72V8h4.12c2.3,0,3.57,1.22,3.62,3.28C77.46,13.21,76.19,14.48,73.84,14.48Z"></path><path d="M99.2,6l-6,15.27H85V6H82.8V23.29H94.7l2-5.19h7.09l2,5.19H108L101.26,6ZM97.39,16.14l2.84-7.39L103,16.14Z"></path><polygon points="113.98 14.18 108.99 6.01 106.59 6.01 112.81 16.14 112.81 23.29 115.01 23.29 115.01 16.14 121.33 6.01 118.98 6.01 113.98 14.18"></polygon><polygon points="123.14 23.29 134.1 23.29 134.1 21.28 125.29 21.28 125.29 15.41 133.32 15.41 133.32 13.45 125.29 13.45 125.29 7.97 134.1 7.97 134.1 6.01 123.14 6.01 123.14 23.29"></polygon><path d="M144.86,15.85c2.74-.39,4.41-2,4.41-4.85,0-3.23-2.26-5-5.73-5h-6.32V23.29h2.22V16h3.08l4.94,7.29H150Zm-5.42-1.71V8h4.06c2.3,0,3.62,1.17,3.62,3.08s-1.32,3.09-3.62,3.09Z"></path><path d="M27.63.09a1,1,0,0,0-1.32.48c-.24.51-6.35,15.3-6.35,15.3-.2.46-.33.41-.33-.07,0,0,0-5.15,0-9.39,0-2.31-1.12-3.61-2.73-3.88A3.12,3.12,0,0,0,14.83,3a4.57,4.57,0,0,0-1.5,1.79c-.48.94-3.47,9.66-3.47,9.66-.16.46-.31.44-.31,0,0,0-.09-3.76-.18-4.64-.13-1.36-.44-3.59-2.2-3.7S4.77,8,4.36,9.24c-.29.84-1.65,5.35-1.65,5.35l-.2.46h0c-.06.24-.17.24-.24,0l-.11-.42Q2,14,1.74,13.31a1.71,1.71,0,0,0-.33-.66.83.83,0,0,0-.88-.22.82.82,0,0,0-.53.69,4.22,4.22,0,0,0,.07.79,29,29,0,0,0,1,4.6,1.31,1.31,0,0,0,1.8.66,3.43,3.43,0,0,0,1.24-1.81c.33-.81,2-5.48,2-5.48.18-.46.31-.44.29,0,0,0-.09,4.57-.09,6.64a13.11,13.11,0,0,0,.28,2.93,2.41,2.41,0,0,0,.82,1.27,2,2,0,0,0,1.41.4,2,2,0,0,0,.7-.24,3.15,3.15,0,0,0,.79-.71,12.52,12.52,0,0,0,1.26-2.11c.81-1.6,2.92-6.58,2.92-6.58.2-.46.33-.41.33.07,0,0-.26,8.36-.26,11.55a6.39,6.39,0,0,0,.44,2.33,2.8,2.8,0,0,0,1.45,1.61A2.57,2.57,0,0,0,18.79,29a3.76,3.76,0,0,0,1.28-1.32,15.12,15.12,0,0,0,1.07-2.31c.64-1.65,1.17-3.33,1.7-5s5-17.65,5.28-19a1.79,1.79,0,0,0,0-.46A1,1,0,0,0,27.63.09Z"></path></svg>'}},r={};function u(e){var t=r[e];if(void 0!==t)return t.exports;var i=r[e]={id:e,loaded:!1,exports:{}};return n[e].call(i.exports,i,i.exports,u),i.loaded=!0,i.exports}u.m=n,u.n=e=>{var t=e&&e.__esModule?()=>e.default:()=>e;return u.d(t,{a:t}),t},u.d=(e,t)=>{for(var n in t)u.o(t,n)&&!u.o(e,n)&&Object.defineProperty(e,n,{enumerable:!0,get:t[n]})},u.f={},u.e=e=>Promise.all(Object.keys(u.f).reduce(((t,n)=>(u.f[n](e,t),t)),[])),u.u=e=>({63:"polyfills.webvtt",74:"jwplayer.controls.tizen",98:"provider.hlsjs",168:"jwplayer.amp",207:"jwplayer.core.controls.html5",250:"provider.html5",347:"vttparser",365:"related",371:"provider.shaka",493:"jwplayer.core.controls.polyfills",520:"provider.airplay",581:"jwplayer.core.controls",605:"jwplayer.core.controls.polyfills.html5",681:"jwplayer.core",716:"jwplayer.controls",926:"jwplayer.stats",943:"polyfills.intersection-observer",977:"provider.cast"}[e]+".js"),u.o=(e,t)=>Object.prototype.hasOwnProperty.call(e,t),e={},t="jwplayer:",u.l=(n,r,i,o)=>{if(e[n])e[n].push(r);else{var s,a;if(void 0!==i)for(var c=document.getElementsByTagName("script"),l=0;l<c.length;l++){var d=c[l];if(d.getAttribute("src")==n||d.getAttribute("data-webpack")==t+i){s=d;break}}s||(a=!0,(s=document.createElement("script")).charset="utf-8",s.timeout=55,u.nc&&s.setAttribute("nonce",u.nc),s.setAttribute("data-webpack",t+i),s.src=n),e[n]=[r];var f=(t,r)=>{s.onerror=s.onload=null,clearTimeout(D);var u=e[n];if(delete e[n],s.parentNode&&s.parentNode.removeChild(s),u&&u.forEach((e=>e(r))),t)return t(r)},D=setTimeout(f.bind(null,void 0,{type:"timeout",target:s}),55e3);s.onerror=f.bind(null,s.onerror),s.onload=f.bind(null,s.onload),a&&document.head.appendChild(s)}},u.r=e=>{"undefined"!=typeof Symbol&&Symbol.toStringTag&&Object.defineProperty(e,Symbol.toStringTag,{value:"Module"}),Object.defineProperty(e,"__esModule",{value:!0})},u.nmd=e=>(e.paths=[],e.children||(e.children=[]),e),u.p="",(()=>{var e={313:0};u.f.j=(t,n)=>{var r=u.o(e,t)?e[t]:void 0;if(0!==r)if(r)n.push(r[2]);else{var i=new Promise(((n,u)=>r=e[t]=[n,u]));n.push(r[2]=i);var o=u.p+u.u(t),s=new Error;u.l(o,(n=>{if(u.o(e,t)&&(0!==(r=e[t])&&(e[t]=void 0),r)){var i=n&&("load"===n.type?"missing":n.type),o=n&&n.target&&n.target.src;s.message="Loading chunk "+t+" failed.\n("+i+": "+o+")",s.name="ChunkLoadError",s.type=i,s.request=o,r[1](s)}}),"chunk-"+t,t)}};var t=(t,n)=>{var r,i,o=n[0],s=n[1],a=n[2],c=0;if(o.some((t=>0!==e[t]))){for(r in s)u.o(s,r)&&(u.m[r]=s[r]);if(a)a(u)}for(t&&t(n);c<o.length;c++)i=o[c],u.o(e,i)&&e[i]&&e[i][0](),e[i]=0},n=self.webpackChunkjwplayer=self.webpackChunkjwplayer||[];n.forEach(t.bind(null,0)),n.push=t.bind(null,n.push.bind(n))})(),u.nc=void 0;var i=u(6577);window.jwplayer=i.default})();
var PathHelpers = {
  getParamValue: function(urlString=window.location.href, param) {
    urlObj = new URL(urlString);
    return urlObj.searchParams.get(param);
  },

  addParamsToQueryString: function(urlString=window.location.href, additions={}) {
    var urlObj = new URL(urlString);
    Object.entries(additions).forEach(pair => {
      urlObj.searchParams.set(pair[0], pair[1]);
    });

    return urlObj.toString()
  },

  removeParamFromQueryString: function(urlString=window.location.href, queryKey) {
    var urlObj = new URL(urlString);
    let queryParams = new URLSearchParams(urlObj.search);
    queryParams.delete(queryKey);
    return urlObj.origin + urlObj.pathname + '?' + queryParams.toString();
  },

  addendPathnameSegmentToUrl: function(urlString=window.location.href, addendum) {
    let urlObj = new URL(urlString);
    urlObj.pathname = urlObj.pathname + addendum;
    return urlObj.toString();
  },

  videoIdFromUrl: function(urlString=window.location.href) {
    const url = urlString.toLowerCase();

    const regex = /(media|stream)\/\d+/;
    const found = url.match(regex);

    if (found !== null) {
      const id = found[0].split('/').pop();
      return id;
    } else {
      // was not found, no media/stream segment in url
      return;
    }
  },

  videoTypeFromUrl: function(urlString=window.location.href) {
    if (urlString.toLowerCase().includes('media')) {
      return 'medium'
    } else if (urlString.toLowerCase().includes('stream')) {
      return 'stream'
    } else {
      return
    }
  },

  collectionTypeFromUrl: function(urlString=window.location.href) {
    const url = urlString.toLowerCase();
    if (url.includes('series')) {
      return 'series'
    } else if (url.includes('playlists')) {
      return 'playlist'
    } else if (url.includes('categories')) {
      return 'category'
    } else {
      return
    }
  },

  collectionIdFromUrl: function(urlString=window.location.href) {
    const url = urlString.toLowerCase();
    const regex = /(series|playlists|categories)\/\d+/;
    const found = url.match(regex);

    if (found !== null) {
      const id = found[0].split('/').pop();
      return id;
    } else {
      // was not found, no collection type in url
      return;
    }

  },

  playerBaseRelUrl: function(urlString=window.location.href) {
    const regex = /player\/[a-z0-9_-]+/i;
    const found = urlString.match(regex);

    if (found !== null) {
      const id = found[0].split('/').pop();
      return `/player/${id}/`;
    } else {
      // was not found, no player key in url
      return;
    }
  },

  playerBaseAbsUrl: function(urlString=window.location.href) {
    const urlObj = new URL(urlString);




    const regex = /player\/[a-z0-9_-]+/i;
    const found = urlString.match(regex);

    if (found !== null) {
      const id = found[0].split('/').pop();
      return `${urlObj.origin}/player/${id}/`;
    } else {
      // was not found, player key in url
      return;
    }
  }


};
var Player = {
  fullScreen: false,
  hasSearchableCaptions: false,
  chapterStartTime: null,
  bufferingSince: null,
  setupData: {},

  setupJwPlayer: function(){
    jwplayer('jw_player_instance').setup(Player.setupData)
      .on('playlistItem', ActivityTracker.onPlaylistItem)
      .on('play', ActivityTracker.onPlay)
      .on('play', function(){
        Player.bufferingSince = null;
      })
      .on('pause', ActivityTracker.onPause)
      .on('buffer', ActivityTracker.onBuffer)
      .on('buffer', Player.handleStalledStream)
      .on('idle', ActivityTracker.onIdle)
      .on('error', ActivityTracker.onError.bind(this))
      .on('error', Player.errorHandling)
      .on('setupError', Player.errorHandling)
      .on('complete', ActivityTracker.onComplete)
      .on('time', ActivityTracker.onTime.bind(this))
      .on('seek', ActivityTracker.onSeek.bind(this))
      .on('ready', function(){
        // this cannot be called sooner as pause will not work, setup will trigger
        // playout after the pause() is called
        Player.restorePriorState();
        if (!HelperFuncs.inIframe() || Player.setupData.autofocus) {
          this.getContainer().focus();
        }

        // handle direct chapter link
        if (Player.chapterStartTime) {
          jwplayer('jw_player_instance').seek(Player.chapterStartTime);

          if (!Player.setupData.autoplay) {
            jwplayer('jw_player_instance').pause();
          }
        }

        Player.removeProblematicHtml();
      });

    ActivityTracker.initializeAnalyticsLibrary();

    if (Player.fullScreen) {
      jwplayer('jw_player_instance').setFullscreen();
    }

    // If user closes browser, want to make sure we send analytics events if we can.
    try { window.attachEvent("onbeforeunload", (u) => { ActivityTracker.handleVideoEvent('video_stop', true) }) } catch (e) {}
    try { window.addEventListener("beforeunload", (u) => { ActivityTracker.handleVideoEvent('video_stop', true) }, false) } catch (e) {}
    // onbeforeunload and beforeunload are not supported on mobile.
    // pagehide should work on mobile. Keep onbeforeunload and beforeunload
    // in place just to be sure removing does not cause an issue on some
    // browsers, though it does risk a race condition with multiple stops.
    // Multiple stops better than none, and can remove if we determine
    // pagehide is comprehensive enough to cover all.
    try { window.addEventListener("pagehide", (u) => { ActivityTracker.handleVideoEvent('video_stop', true) }, false) } catch (e) {}

    // handle truly stalled player, if no play event in 20 seconds, reload and enter retries UI
    if (Player.setupData.liveStream && Player.setupData.enableLiveStaleCheck) {
      setInterval(() => {
        if (Player.bufferingSince && Date.now() - Player.bufferingSince > 8000) {
          window.location.reload();
        }
      }, 5000); // don't execute this more often as the manifest check can take a few seconds, shorter intervals result in endless reloads
    }
  },

  addDownloadButtonToPlayer: function() {
    if (!Player.setupData.showDownloadButton) return;
    jwplayer('jw_player_instance').addButton(
      // svg comes from www.fontawesome.com
      '<svg xmlns="http://www.w3.org/2000/svg" class="jw-svg-icon jw-svg-icon-sharing" viewBox="0 0 512 512"><path d="M216 0h80c13.3 0 24 10.7 24 24v168h87.7c17.8 0 26.7 21.5 14.1 34.1L269.7 378.3c-7.5 7.5-19.8 7.5-27.3 0L90.1 226.1c-12.6-12.6-3.7-34.1 14.1-34.1H192V24c0-13.3 10.7-24 24-24zm296 376v112c0 13.3-10.7 24-24 24H24c-13.3 0-24-10.7-24-24V376c0-13.3 10.7-24 24-24h146.7l49 49c20.1 20.1 52.5 20.1 72.6 0l49-49H488c13.3 0 24 10.7 24 24zm-124 88c0-11-9-20-20-20s-20 9-20 20 9 20 20 20 20-9 20-20zm64 0c0-11-9-20-20-20s-20 9-20 20 9 20 20 20 20-9 20-20z"/></svg>', //served out of Rails root/public dir
      'Download Video',
      function(){
        window.location = Player.setupData.downloadUrl;
      },
      'download'
    );
  },

  addCaptionViewButtonToPlayer: function() {
    // the video has closed captions or 608 extracted captions that can be searched
    if (Player.hasSearchableCaptions) {
      jwplayer('jw_player_instance').addButton(
        '<svg class="jw-svg-icon jw-svg-icon-sharing" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="400" height="370.6959706959707" viewBox="0, 0, 400,370.6959706959707"><g id="svgg"><path id="path0" d="M35.478 28.019 C 31.688 29.895,27.331 33.816,24.489 37.908 L 19.780 44.689 19.780 189.233 L 19.780 333.778 24.393 340.146 C 26.930 343.648,31.814 347.999,35.246 349.814 L 41.487 353.114 141.669 353.114 C 252.185 353.114,247.209 353.521,256.749 343.698 C 266.351 333.811,265.592 332.296,250.142 330.520 C 246.291 330.077,238.200 328.057,232.162 326.030 L 221.184 322.344 135.500 322.344 L 49.817 322.344 49.817 189.011 L 49.817 55.678 101.099 55.678 L 152.381 55.678 152.381 92.420 L 152.381 129.163 156.664 133.446 L 160.947 137.729 191.285 137.729 C 219.661 137.729,222.257 137.500,231.414 134.197 C 236.799 132.255,244.462 130.248,248.441 129.737 C 252.421 129.227,257.821 128.478,260.440 128.074 L 265.201 127.340 265.201 114.905 C 265.201 106.978,264.377 100.496,262.926 97.024 C 259.832 89.618,202.060 31.401,194.139 27.706 C 184.460 23.192,44.674 23.468,35.478 28.019 M231.327 106.593 C 231.692 106.795,221.001 106.960,207.570 106.960 L 183.150 106.960 183.150 83.167 L 183.150 59.375 206.907 82.801 C 219.974 95.685,230.963 106.392,231.327 106.593 M244.152 150.310 C 217.314 156.806,192.541 181.585,185.471 209.003 C 167.818 277.471,239.060 334.917,302.538 303.400 L 311.355 299.023 338.549 326.068 C 370.265 357.610,370.749 357.841,381.878 346.713 C 393.014 335.576,392.795 335.117,361.066 303.228 L 333.853 275.879 336.913 270.906 C 374.044 210.567,314.583 133.262,244.152 150.310 M286.447 184.528 C 325.603 202.427,325.312 257.401,285.964 275.883 C 244.410 295.401,199.551 250.759,219.281 209.524 C 231.991 182.963,260.122 172.493,286.447 184.528 M67.194 196.153 L 60.395 202.930 60.395 219.780 L 60.395 236.630 67.194 243.305 L 73.993 249.980 87.197 250.336 C 101.829 250.730,108.303 248.886,114.132 242.664 C 116.063 240.604,118.300 239.325,119.105 239.822 C 121.483 241.292,115.311 231.601,111.719 228.226 L 108.419 225.125 102.034 228.313 C 93.704 232.474,88.635 232.358,84.182 227.905 C 80.761 224.484,79.399 224.528,81.707 227.986 C 85.442 233.579,94.643 234.313,102.895 229.675 L 108.753 226.382 112.985 231.451 C 115.312 234.238,117.216 237.192,117.216 238.014 C 117.216 238.836,115.544 237.047,113.500 234.040 C 109.198 227.708,108.649 227.584,102.233 231.496 C 89.478 239.273,75.623 230.344,78.300 216.072 C 80.206 205.911,94.749 202.096,105.277 208.994 C 109.423 211.711,110.449 210.883,115.848 200.459 L 118.646 195.057 115.052 192.229 C 111.928 189.773,108.999 189.400,92.725 189.389 L 73.993 189.376 67.194 196.153 M128.825 195.151 C 112.044 211.436,114.376 237.675,133.530 248.108 L 138.462 250.794 134.799 247.774 C 132.784 246.113,130.531 244.739,129.792 244.721 C 129.054 244.703,128.794 244.344,129.216 243.922 C 129.638 243.500,132.880 244.811,136.420 246.835 C 145.552 252.054,160.566 252.067,169.963 246.863 L 176.557 243.211 172.161 247.011 C 169.461 249.345,168.942 250.225,170.816 249.294 C 177.794 245.829,179.100 234.127,173.171 228.198 L 170.051 225.078 163.280 228.460 C 155.620 232.285,147.113 231.903,143.961 227.592 C 142.951 226.211,142.125 225.829,142.125 226.743 C 142.125 232.647,156.146 234.821,163.370 230.037 C 169.182 226.188,170.627 226.344,173.545 231.136 L 175.998 235.165 172.850 231.544 L 169.702 227.924 164.048 231.178 C 152.065 238.075,141.022 233.518,139.622 221.099 C 138.131 207.871,149.364 201.858,163.892 208.108 C 168.086 209.912,171.188 211.718,170.785 212.121 C 170.382 212.524,166.618 211.376,162.420 209.570 C 149.646 204.075,139.676 209.045,141.070 220.214 L 141.656 224.908 141.890 219.641 C 142.324 209.903,152.973 206.360,164.822 212.010 C 172.107 215.484,176.256 211.561,176.641 200.834 C 177.030 190.015,175.768 189.389,153.492 189.357 L 134.823 189.330 128.825 195.151 M72.776 194.254 C 69.718 196.332,65.941 200.123,64.383 202.679 C 62.824 205.235,61.547 206.415,61.544 205.302 C 61.537 202.686,73.721 190.476,76.338 190.476 C 77.437 190.476,75.834 192.176,72.776 194.254 M114.286 193.407 C 116.300 194.982,117.393 196.286,116.715 196.304 C 116.036 196.322,113.804 195.018,111.755 193.407 C 109.706 191.795,108.613 190.491,109.326 190.509 C 110.039 190.527,112.271 191.831,114.286 193.407 M135.531 193.217 C 119.274 203.314,115.085 225.949,127.031 239.149 C 128.338 240.594,129.031 242.154,128.570 242.615 C 126.785 244.400,119.660 229.454,118.995 222.529 C 117.836 210.468,129.742 190.457,138.063 190.482 C 139.088 190.485,137.949 191.716,135.531 193.217 M114.475 205.274 C 110.856 211.095,109.271 212.507,107.296 211.670 C 89.343 204.052,76.338 208.315,79.554 220.763 C 80.016 222.553,80.303 222.104,80.416 219.414 C 80.800 210.306,92.254 206.580,103.485 211.909 C 109.453 214.741,112.534 212.835,117.402 203.297 C 121.372 195.517,119.937 196.487,114.475 205.274 M174.359 208.059 C 173.423 209.808,172.334 210.918,171.941 210.525 C 171.547 210.131,172.070 208.456,173.103 206.803 C 175.545 202.893,176.573 203.921,174.359 208.059 M72.776 245.306 C 75.834 247.384,77.437 249.084,76.338 249.084 C 73.721 249.084,61.537 236.874,61.544 234.259 C 61.547 233.145,62.824 234.326,64.383 236.881 C 65.941 239.437,69.718 243.228,72.776 245.306 M112.236 246.254 C 109.095 248.617,107.141 250.549,107.896 250.549 C 108.651 250.549,111.551 248.598,114.341 246.213 C 120.832 240.665,119.638 240.689,112.236 246.254 " stroke="none"></path></g></svg>',
        'View/Search Captions',
        function(){
          // set player state in session for later reading:
          Player.setPlayerStateInSession();
          
          // button should toggle between caption view and normal video view
          // if in caption view, go to normal video view, if in video view
          // go to caption view
          let currentUrl = window.location.href;
          if (currentUrl.includes("captions_view=t")) {
            window.location = PathHelpers.removeParamFromQueryString(currentUrl, 'captions_view')
          } else {
            window.location = PathHelpers.addParamsToQueryString(currentUrl, { 'captions_view': 't' } )
          }
        },
        'view_captions'
      );

    } else {
      jwplayer('jw_player_instance').removeButton('view_captions');
    }
  },

  addAgendaViewButtonToPlayer: function() {
    if (!Player.setupData.hasAgenda) return;
    // svg grabbed from here: https://github.com/FortAwesome/Font-Awesome/blob/6.x/svgs/solid
    jwplayer('jw_player_instance').addButton(
      '<svg class="jw-svg-icon jw-svg-icon-sharing" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 6.1.2 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2022 Fonticons, Inc. --><path d="M152.1 38.16C161.9 47.03 162.7 62.2 153.8 72.06L81.84 152.1C77.43 156.9 71.21 159.8 64.63 159.1C58.05 160.2 51.69 157.6 47.03 152.1L7.029 112.1C-2.343 103.6-2.343 88.4 7.029 79.03C16.4 69.66 31.6 69.66 40.97 79.03L63.08 101.1L118.2 39.94C127 30.09 142.2 29.29 152.1 38.16V38.16zM152.1 198.2C161.9 207 162.7 222.2 153.8 232.1L81.84 312.1C77.43 316.9 71.21 319.8 64.63 319.1C58.05 320.2 51.69 317.6 47.03 312.1L7.029 272.1C-2.343 263.6-2.343 248.4 7.029 239C16.4 229.7 31.6 229.7 40.97 239L63.08 261.1L118.2 199.9C127 190.1 142.2 189.3 152.1 198.2V198.2zM224 96C224 78.33 238.3 64 256 64H480C497.7 64 512 78.33 512 96C512 113.7 497.7 128 480 128H256C238.3 128 224 113.7 224 96V96zM224 256C224 238.3 238.3 224 256 224H480C497.7 224 512 238.3 512 256C512 273.7 497.7 288 480 288H256C238.3 288 224 273.7 224 256zM160 416C160 398.3 174.3 384 192 384H480C497.7 384 512 398.3 512 416C512 433.7 497.7 448 480 448H192C174.3 448 160 433.7 160 416zM0 416C0 389.5 21.49 368 48 368C74.51 368 96 389.5 96 416C96 442.5 74.51 464 48 464C21.49 464 0 442.5 0 416z"/></svg>',
      'Agenda View',
      function(){
        // set player state in session for later reading:
        Player.setPlayerStateInSession();
        
        // button should toggle between caption view and normal video view
        // if in caption view, go to normal video view, if in video view
        // go to caption view
        let currentUrl = window.location.href;
        if (currentUrl.includes("agenda_view")) {
          window.location = PathHelpers.removeParamFromQueryString(currentUrl, 'agenda_view');
        } else {
          window.location  = PathHelpers.addParamsToQueryString(currentUrl, { 'agenda_view': 't' })
        }
      },
      'view_agenda'
    );
  },

  addChannelGuideButtonToPlayer: function() {
    if (!Player.setupData.showChannelGuide) return;

    jwplayer('jw_player_instance').addButton(
      '<svg width="20px" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!-- Font Awesome Free 5.15.4 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) --><path fill="currentColor" d="M148 288h-40c-6.6 0-12-5.4-12-12v-40c0-6.6 5.4-12 12-12h40c6.6 0 12 5.4 12 12v40c0 6.6-5.4 12-12 12zm108-12v-40c0-6.6-5.4-12-12-12h-40c-6.6 0-12 5.4-12 12v40c0 6.6 5.4 12 12 12h40c6.6 0 12-5.4 12-12zm96 0v-40c0-6.6-5.4-12-12-12h-40c-6.6 0-12 5.4-12 12v40c0 6.6 5.4 12 12 12h40c6.6 0 12-5.4 12-12zm-96 96v-40c0-6.6-5.4-12-12-12h-40c-6.6 0-12 5.4-12 12v40c0 6.6 5.4 12 12 12h40c6.6 0 12-5.4 12-12zm-96 0v-40c0-6.6-5.4-12-12-12h-40c-6.6 0-12 5.4-12 12v40c0 6.6 5.4 12 12 12h40c6.6 0 12-5.4 12-12zm192 0v-40c0-6.6-5.4-12-12-12h-40c-6.6 0-12 5.4-12 12v40c0 6.6 5.4 12 12 12h40c6.6 0 12-5.4 12-12zm96-260v352c0 26.5-21.5 48-48 48H48c-26.5 0-48-21.5-48-48V112c0-26.5 21.5-48 48-48h48V12c0-6.6 5.4-12 12-12h40c6.6 0 12 5.4 12 12v52h128V12c0-6.6 5.4-12 12-12h40c6.6 0 12 5.4 12 12v52h48c26.5 0 48 21.5 48 48zm-48 346V160H48v298c0 3.3 2.7 6 6 6h340c3.3 0 6-2.7 6-6z"/></svg>',
      'Channel Guide',
      function(){
        Player.setPlayerStateInSession();
        let currentUrl = window.location.href;
        if (currentUrl.includes("schedule_view")) {
          window.location = PathHelpers.removeParamFromQueryString(currentUrl, 'schedule_view');
        } else {
          window.location  = PathHelpers.addParamsToQueryString(currentUrl, { 'schedule_view': 't' })
        }
      },
      'view_channel_guide'
    );
  },

  setPlayerStateInSession: function() {
    let state = jwplayer('jw_player_instance').getState(); // playing, paused, idle or buffering
    let pos = jwplayer('jw_player_instance').getPosition(); // in in secs with decimal: x.xxx secs
    if (state == 'idle') { state = 'paused' };
    if (state == 'buffering') { state = 'playing' };
    sessionStorage.setItem("player.playState", state); // playing or paused
    sessionStorage.setItem("player.playPosition", pos); // time in seconds
  },

  retrievePlayerStateFromSession: function() {
    return { 
      state: sessionStorage.getItem("player.playState"), // playing or paused
      pos: sessionStorage.getItem("player.playPosition") // in in secs with decimal: x.xxx secs
    };
  },

  clearPlayerStateFromSession: function() {
    sessionStorage.removeItem("player.playState");
    sessionStorage.removeItem("player.playPosition");
  },

  shouldSyncVideoAndCaptions: function() {
    return document.querySelector('input#synch_video_and_captions:checked') !== null;
  },

  restorePriorState: function() {
    let previousPlayerState = Player.retrievePlayerStateFromSession();

    if (previousPlayerState.pos) {
      jwplayer('jw_player_instance').seek(parseFloat(previousPlayerState.pos));
    }

    if (previousPlayerState.state == 'playing') {
      jwplayer('jw_player_instance').play();
    } else if (previousPlayerState.state == 'paused') {
      jwplayer('jw_player_instance').pause();
    }

    Player.clearPlayerStateFromSession();
  },

  initializeBootstrapMouseOvers: function() {
    // yes there's jquery in here, bootstrap uses jquery
    $("a[rel~=popover], .has-popover").popover();
    $("a[rel~=tooltip], .has-tooltip").tooltip();
  },

  addListenersToMainNavItems: function() {
    if (shouldHideSpinner()) {
      return
    }
    
    const navItems = document.querySelectorAll('ul#tabs li');

    navItems.forEach(navItem => { 
      navItem.addEventListener('click', (e) => {
        const mainHtml = document.querySelector('main.tab-pane.active.container');
        // loading spinner animated gif
        mainHtml.innerHTML = "<img src='/static-assets/loading-ef853dd827d3038e752a80fa8add43fe7d2dcfba5a4c84f5e7125da97a297818.gif' style='width: 30px;' />";
        mainHtml.style.textAlign = 'center';
      });
    });

    function shouldHideSpinner() {
      // iOS does not display the spinner correctly, do not show
      let currentUrl = window.location.href;
      if (currentUrl.toLowerCase().includes("os=ios")) {
        return true
      } else {
        return false
      }
    }
  },

  removeProblematicHtml: function() {
    // jwplayer injects html attributes which can be problematic for accessibility
    //   ideally we'd want to remove these via jwplayer configuration, but since
    //   these can't be done that way, instead after player is setup, remove it
    //   with js
    const playerInst = document.querySelector('div#jw_player_instance');
    const tabindex = playerInst.getAttributeNode('tabindex');
    const role = playerInst.getAttributeNode('role');
    const ariaLabel = playerInst.getAttributeNode('aria-label');
    playerInst.removeAttributeNode(tabindex);
    playerInst.removeAttributeNode(role);
    playerInst.removeAttributeNode(ariaLabel);
  },

  mobileAppPlayerSetup: function(tokenized_playout_url) {
    Player.setupData.playlist[0].file = tokenized_playout_url;
    Player.setupData.controls = true;
    Player.setupJwPlayer();
  },

  errorHandling: function(event) {
    console.log(event.code);
    
    if ([232400, 232600].includes(event.code) && Player.setupData.enableLiveStaleCheck && Player.setupData.liveStream) {
      window.location.reload();
    }
  },

  handleStalledStream: function(event) {
    Player.bufferingSince = Date.now();
  }
  


};

document.addEventListener("DOMContentLoaded", function(){
  Player.initializeBootstrapMouseOvers();
  Player.addListenersToMainNavItems();
  
  if (document.querySelector('div#jw_player_instance') != null) {
    if (Player.setupData.streamIsPlayable) {
      Player.setupJwPlayer();
    }
    
    Player.addDownloadButtonToPlayer();
    Player.addCaptionViewButtonToPlayer();
    Player.addAgendaViewButtonToPlayer();
    Player.addChannelGuideButtonToPlayer()
    
  }
});
var Playlists = {
  // playlists with more than 50 items are loaded by breaking up the load into
  //  chunks of 50 playlist items using multiple client side requests
  loadAdditionalPlaylistItems: function(totalItemCount, container) {
    const additionalItemsToRequest = totalItemCount - 50;
    const numRequests = Math.ceil(additionalItemsToRequest / 50);
    const playerRelUrl = PathHelpers.playerBaseRelUrl();
    const playlistId = PathHelpers.collectionIdFromUrl();


    async function loadItemsSequentially(totalRequests) {
      for (let n = 1; n <= totalRequests; n++) {
        try {
          const response = await fetch(`${playerRelUrl}playlists/${playlistId}/playlist_items?offset=${50 * n}`, {
            headers: {
              "Accept": "text/html",
              "X-Requested-With": "XMLHttpRequest"
            }
          });

          if (response.ok) {
            const html = await response.text();
            // Inject raw HTML chunk directly into the DOM
            container.insertAdjacentHTML("beforeend", html);
          } else {
            console.error(`Failed to load page ${n + 1}`);
          }
        } catch (error) {
          console.error(`Error loading page ${n + 1}:`, error);
        }
      }
    }

    loadItemsSequentially(numRequests);
  },

  addListenersToShowHideControls: function(container) {
    container.addEventListener("click", function(event) {
      const button = event.target.closest("button.show-attachments-link");
      if (!button) return;

      event.preventDefault();

      const summary = button.parentElement.querySelector(".summary");
      $(summary).slideToggle();
      button.textContent = button.textContent === "Show More" ? "Hide More" : "Show More";
    });
  }



};

document.addEventListener("DOMContentLoaded", function(){
  const container = document.querySelector('ol#collection-items');

  if (HelperFuncs.bodyHasClass(['playlists-show', 'playlists-show_with_video'])) {

    Playlists.addListenersToShowHideControls(container);

    const playlistItemCount = Number(
      document.querySelector('[data-playlist-item-count]').dataset.playlistItemCount
    );

    if (playlistItemCount > 50) {
      const playlistId = "";
      const playerAccessKey = "";


      Playlists.loadAdditionalPlaylistItems(playlistItemCount, container);
    }
  }
  
});
/*!
   JW Player version 8.38.8
   Copyright (c) 2025, JW Player, All Rights Reserved
   This source code and its use and distribution is subject to the terms
   and conditions of the applicable license agreement.
   https://www.jwplayer.com/tos/
   This product includes portions of other software. For the full text of licenses, see
   https://ssl.p.jwpcdn.com/player/v/8.38.8/notice.txt
*/
"use strict";(self.webpackChunkjwplayer=self.webpackChunkjwplayer||[]).push([[520],{6342:(e,t,a)=>{a.r(t),a.d(t,{default:()=>l});var i=a(9888);function l(e,t){let a=null;const l=this,c=function(){t.set("castState",{available:t.get("castAvailable"),active:t.get("castActive")})},n=function(e){e&&e.forEach((function(e){e.file=(0,i.getAbsolutePath)(e.file)}))},s=function(e){e&&(e.image=(0,i.getAbsolutePath)(e.image),n(e.allSources),n(e.sources))};l.updateAvailability=function(e){t.set("castAvailable","available"===e.availability),c()},l.updateActive=function(){let i=!1;a&&(i=Boolean(a.webkitCurrentPlaybackTargetIsWireless)),t.off("change:playlistItem",s),i&&(e.instreamDestroy(),s(t.get("playlistItem")),t.on("change:playlistItem",s)),t.set("airplayActive",i),t.set("castActive",i),c()},l.airplayToggle=function(){a&&a.webkitShowPlaybackTargetPicker()},t.change("itemReady",(function(){a=null,t.getVideo()&&(a=t.getVideo().video),a&&(a.removeAttribute("disableRemotePlayback"),a.removeEventListener("webkitplaybacktargetavailabilitychanged",l.updateAvailability),a.removeEventListener("webkitcurrentplaybacktargetiswirelesschanged",l.updateActive),a.addEventListener("webkitplaybacktargetavailabilitychanged",l.updateAvailability),a.addEventListener("webkitcurrentplaybacktargetiswirelesschanged",l.updateActive)),l.updateAvailability({}),l.updateActive()}))}}}]);
/*!
   JW Player version 8.38.8
   Copyright (c) 2025, JW Player, All Rights Reserved
   This source code and its use and distribution is subject to the terms
   and conditions of the applicable license agreement.
   https://www.jwplayer.com/tos/
   This product includes portions of other software. For the full text of licenses, see
   https://ssl.p.jwpcdn.com/player/v/8.38.8/notice.txt
*/
"use strict";(self.webpackChunkjwplayer=self.webpackChunkjwplayer||[]).push([[977],{3328:(e,t,s)=>{s.d(t,{Z:()=>_});var i=s(6103),a=s(8377);const r={TIT2:"title",TT2:"title",WXXX:"url",TPE1:"artist",TP1:"artist",TALB:"album",TAL:"album"},n=(e,t)=>{const s=e.length;let i,a,r,n="",d=t||0;for(;d<s;)if(i=e[d++],0!==i&&3!==i)switch(i>>4){case 0:case 1:case 2:case 3:case 4:case 5:case 6:case 7:n+=String.fromCharCode(i);break;case 12:case 13:a=e[d++],n+=String.fromCharCode((31&i)<<6|63&a);break;case 14:a=e[d++],r=e[d++],n+=String.fromCharCode((15&i)<<12|(63&a)<<6|63&r)}return n},d=e=>{const t=(e=>{let t="0x";for(let s=0;s<e.length;s++)e[s]<16&&(t+="0"),t+=e[s].toString(16);return parseInt(t,16)})(e);return 127&t|(32512&t)>>1|(8323072&t)>>2|(2130706432&t)>>3},o=e=>{const t={};if(!("value"in e)&&"data"in e&&e.data instanceof ArrayBuffer){const t=new Uint8Array(e.data);let s=t.length;e={value:{key:"",data:""}};let i=10;for(;i<14&&i<t.length&&0!==t[i];)e.value.key+=String.fromCharCode(t[i]),i++;let a=19,r=t[a];3!==r&&0!==r||(r=t[++a],s--);let o=0;if(1!==r&&2!==r)for(let e=a+1;e<s;e++)if(0===t[e]){o=e-a;break}if(o>0){const s=n(t.subarray(a,a+=o),0);if("PRIV"===e.value.key){if("com.apple.streaming.transportStreamTimestamp"===s){const s=1&d(t.subarray(a,a+=4)),i=d(t.subarray(a,a+=4))+(s?4294967296:0);e.value.data=i}else e.value.data=n(t,a+1);e.value.info=s}else e.value.info=s,e.value.data=n(t,a+1)}else{const s=t[a];e.value.data=1===s||2===s?((e,t)=>{const s=e.length-1;let i="",a=t||0;for(;a<s;)254===e[a]&&255===e[a+1]||(i+=String.fromCharCode((e[a]<<8)+e[a+1])),a+=2;return i})(t,a+1):n(t,a+1)}}if(function(e,t){if(null==e)throw new TypeError("Cannot convert undefined or null to object");return Object.prototype.hasOwnProperty.call(Object(e),t)}(r,e.value.key)&&(t[r[e.value.key]]=e.value.data),e.value.info){let s=t[e.value.key];s!==Object(s)&&(s={},t[e.value.key]=s),s[e.value.info]=e.value.data}else t[e.value.key]=e.value.data;return t};var c=s(8348),l=s(1643),h=s(6042);const u=s(8494).Z.logger.child("jwplayer/providers/tracks-mixin"),m=(e,t,s)=>{null!=t&&t.length&&(0,h.S6)(t,(function(t){const i=t._id||"";if(s&&(t._id=void 0),!c.Browser.ie&&!c.Browser.safari||!e||!/^(native|subtitle|cc)/.test(i)){if(c.Browser.ie&&"disabled"===t.mode||(t.mode="disabled",t.mode="hidden"),t.cues)for(let e=t.cues.length;e--;)t.removeCue(t.cues[e]);t.embedded||(t.mode="disabled"),t.inuse=!1}}))},T=e=>/^native(?:captions|subtitles)/.test(e),g=e=>"captions"===e||"subtitles"===e,k=function(e){const t=e.target,{activeCues:s,cues:i}=t,a=t._id,r=this._cues,n=this._activeCues;if(null!=i&&i.length){const e=r[a];r[a]=Array.prototype.slice.call(i),this.parseNativeID3Cues(i,e)}else delete r[a];if(null!=s&&s.length){const e=n[a],i=n[a]=Array.prototype.slice.call(s);this.triggerActiveCues(i,e,t)}else delete n[a]},v=(e,t,s)=>{if(c.Browser.ie){let i=s;(e||"metadata"===t.kind)&&(i=new window.TextTrackCue(s.startTime,s.endTime,s.text),s.value&&(i.value=s.value)),((e,t)=>{const s=[],i=e.mode;e.mode="hidden";const a=e.cues;if(a)for(let i=a.length-1;i>=0&&a[i].startTime>t.startTime;i--)s.unshift(a[i]),e.removeCue(a[i]);try{e.addCue(t),s.forEach((t=>e.addCue(t)))}catch(e){u.error(e)}e.mode=i})(t,i)}else try{t.addCue(s)}catch(e){u.error(e)}},p=function(e){const t=this._textTracks,s=this._tracksById;if(e.length>t.length)return!0;for(let t=0;t<e.length;t++){const i=e[t];if(!i._id||!s[i._id])return!0}return!1},f=function(){const e=this.video.textTracks,t=(0,h.hX)(e,(function(e){return(e.inuse||!e._id)&&g(e.kind)}));if(!this._textTracks||p.call(this,t))return void this.setTextTracks(e);let s=-1;for(let e=0;e<this._textTracks.length;e++)if("showing"===this._textTracks[e].mode){s=e;break}s!==this._currentTextTrackIndex&&this.setSubtitlesTrack(s+1);const i=e[s];if(i){const e=this.cueChangeHandler=this.cueChangeHandler||k.bind(this);i.removeEventListener("cuechange",e),i.addEventListener("cuechange",e)}},y=function(e){const t=e.track;null!=t&&t._id||this.setTextTracks(this.video.textTracks)},C=(e,t)=>e.startTime===t.startTime&&e.endTime===t.endTime&&e.text===t.text&&e.data===t.data&&JSON.stringify(e.value)===JSON.stringify(t.value),S=e=>{const t=o(e);return{metadataType:"id3",metadataTime:e.startTime,metadata:t}},_={_itemTracks:null,_textTracks:null,_currentTextTrackIndex:-1,_tracksById:null,_cuesByTrackId:null,_cachedVTTCues:null,_metaCuesByTextTime:null,_unknownCount:0,_activeCues:null,_cues:null,textTrackChangeHandler:null,addTrackHandler:null,cueChangeHandler:null,renderNatively:!1,_initTextTracks(){this._textTracks=[],this._tracksById={},this._metaCuesByTextTime={},this._cuesByTrackId={},this._cachedVTTCues={},this._cues={},this._activeCues={},this._unknownCount=0},addTracksListener(e,t,s){e&&(this.removeTracksListener(e,t,s),this.instreamMode||(e.addEventListener?e.addEventListener(t,s):e[`on${t}`]=s))},removeTracksListener(e,t,s){e&&(e.removeEventListener&&s?e.removeEventListener(t,s):e[`on${t}`]=null)},clearTracks(){(0,i.VS)(this._itemTracks);const{_tracksById:e}=this;if(e&&Object.keys(e).forEach((t=>{if(0===t.indexOf("nativemetadata")){const s=e[t];this.cueChangeHandler&&s.removeEventListener("cuechange",this.cueChangeHandler),m(this.renderNatively,[s],!0)}})),this._itemTracks=null,this._textTracks=null,this._tracksById=null,this._cuesByTrackId=null,this._metaCuesByTextTime=null,this._unknownCount=0,this._currentTextTrackIndex=-1,this._activeCues={},this._cues={},this.renderNatively){const e=this.video.textTracks;this.textTrackChangeHandler&&this.removeTracksListener(e,"change",this.textTrackChangeHandler),m(this.renderNatively,e,!0)}},clearMetaCues(){const{_tracksById:e,_cachedVTTCues:t}=this;e&&t&&Object.keys(e).forEach((s=>{if(0===s.indexOf("nativemetadata")){const i=e[s];m(this.renderNatively,[i],!1),i.mode="hidden",i.inuse=!0,i._id&&(t[i._id]={})}}))},clearCueData(e){const t=this._cachedVTTCues;var s;null!=t&&t[e]&&(t[e]={},null!=(s=this._tracksById)&&s[e]&&(this._tracksById[e].data=[]))},disableTextTrack(){const e=this.getCurrentTextTrack();if(e){e.mode="disabled";const t=e._id;(t&&T(t)||this.renderNatively&&c.OS.iOS)&&(e.mode="hidden")}},enableTextTrack(){const e=this.getCurrentTextTrack();e&&(e.mode="showing")},getCurrentTextTrack(){if(this._textTracks)return this._textTracks[this._currentTextTrackIndex]},getSubtitlesTrack(){return this._currentTextTrackIndex},addTextTracks(e){var t;const s=[];return e?(this._textTracks||this._initTextTracks(),e.forEach((e=>{if(e.includedInManifest||e.kind&&!g(e.kind))return;const t=this._createTrack(e);this._addTrackToList(t),s.push(t),e.file&&(e.data=[],(0,i.xl)(e,(e=>{t.sideloaded=!0,this.addVTTCuesToTrack(t,e)}),(e=>{this.trigger(l.cM,e)})))})),null!=this&&null!=(t=this._textTracks)&&t.length&&this.trigger(l.jt,{tracks:this._textTracks}),s):s},setTextTracks(e){var t;if(this._currentTextTrackIndex=-1,e){if(this._textTracks){const e=this._tracksById;this._activeCues={},this._cues={},this._unknownCount=0,this._textTracks=this._textTracks.filter((t=>{const s=t._id;return this.renderNatively&&s&&T(s)?(delete e[s],!1):(t.name&&0===t.name.indexOf("CC")&&this._unknownCount++,0===s.indexOf("nativemetadata")&&"com.apple.streaming"===t.inBandMetadataTrackDispatchType&&delete e[s],!0)}),this)}else this._initTextTracks();if(e.length){let t=0;const s=e.length,i=this._tracksById,r=this._cuesByTrackId;for(;t<s;t++){const s=e[t];let n=s._id||"";if(!n){if(!1===s.inuse&&g(s.kind)&&this.renderNatively){s._id=`native${s.kind}${t}`;continue}if(g(s.kind)||"metadata"===s.kind){if(n=s._id=`native${s.kind}${t}`,!s.label&&"captions"===s.kind){const e=(0,a._)(s,this._unknownCount);s.name=e.label,this._unknownCount=e.unknownCount}}else n=s._id=(0,a.M)(s,this._textTracks?this._textTracks.length:0);if(i[n])continue;s.inuse=!0}if(!s.inuse||i[n])continue;if("metadata"===s.kind)s.mode="hidden",i[n]=s;else if(g(s.kind)){const e=s.mode;let t;if(s.mode="hidden",(!s.cues||!s.cues.length)&&s.embedded)continue;if(("disabled"!==e||T(n))&&(s.mode=e),r[n]&&!r[n].loaded){const i=r[n].cues;for(;t=i.shift();)v(this.renderNatively,s,t);s.mode=e,r[n].loaded=!0}this._addTrackToList(s)}const d=this.cueChangeHandler=this.cueChangeHandler||k.bind(this);s.removeEventListener("cuechange",d),s.addEventListener("cuechange",d)}}this.renderNatively&&this.addTrackListeners(e),null!=this&&null!=(t=this._textTracks)&&t.length&&this.trigger(l.jt,{tracks:this._textTracks})}},addTrackListeners(e){let t=this.textTrackChangeHandler=this.textTrackChangeHandler||f.bind(this);this.removeTracksListener(e,"change",t),this.addTracksListener(e,"change",t),(c.Browser.edge&&c.Browser.ie||c.Browser.firefox)&&(t=this.addTrackHandler=this.addTrackHandler||y.bind(this),this.removeTracksListener(e,"addtrack",t),this.addTracksListener(e,"addtrack",t))},setupSideloadedTracks(e){if(!this.renderNatively)return;const t=(e=e||null)===this._itemTracks;t||(0,i.VS)(this._itemTracks),this._itemTracks=e,e&&(t||(this.disableTextTrack(),this._clearSideloadedTextTracks(),this.addTextTracks(e)))},setSubtitlesTrack(e){if(!this.renderNatively)return void(this.setCurrentSubtitleTrack&&this.setCurrentSubtitleTrack(e-1));if(!this._textTracks)return;if(0===e&&this._textTracks.forEach((e=>{e.mode=e.embedded?"hidden":"disabled"})),this._currentTextTrackIndex===e-1)return;this.disableTextTrack(),this._currentTextTrackIndex=e-1;const t=this.getCurrentTextTrack();if(t){const e=this.cueChangeHandler=this.cueChangeHandler||k.bind(this);t.removeEventListener("cuechange",e),t.addEventListener("cuechange",e),t.mode="showing"}this.trigger(l.UF,{currentTrack:this._currentTextTrackIndex+1,tracks:this._textTracks})},createCue:(e,t,s)=>new(window.VTTCue||window.TextTrackCue)(e,Math.max(t||0,e+.25),s),addVTTCue(e,t){this._tracksById||this._initTextTracks();const s=e.track?e.track:`native${e.type}`;let i=this._tracksById[s];const a="captions"===e.type?"CC":"ID3 Metadata",r=e.cue;if(!i){const t={kind:e.type,_id:s,label:a,default:!1};this.renderNatively||"metadata"===t.kind?(i=this._createTrack(t),i.embedded=!0,this.setTextTracks(this.video.textTracks)):i=this.addTextTracks([t])[0]}if(this._cacheVTTCue(i,r,t)){const e=this.renderNatively||"metadata"===i.kind;return e?v(e,i,r):i.data.push(r),r}return null},addVTTCuesToTrack(e,t){var s,i;if(!this.renderNatively)return;const a=e._id,r=this._tracksById;let n=this._cuesByTrackId;const d=r[a];if(!d)return n||(n=this._cuesByTrackId={}),void(n[a]={cues:t,loaded:!1});if(null!=(s=n)&&null!=(i=s[a])&&i.loaded)return;let o;for(n[a]={cues:t,loaded:!0};o=t.shift();)v(this.renderNatively,d,o)},parseNativeID3Cues(e,t){const s=e[e.length-1];if(t&&t.length===e.length&&(s._parsed||C(t[t.length-1],s)))return;const i=[],a=[];let r=-1,n=-1,d=-1;for(let t=0;t<e.length;t++){const s=e[t];if(!s._extended&&Boolean(s.data||s.value)){if(s.startTime!==n||null===s.endTime){d=n,n=s.startTime;const e=i[r];i[++r]=[],a[r]=[];if(e&&n-d>0)for(let t=0;t<e.length;t++){const s=e[t];s.endTime=n,s._extended=!0}}i[r].push(s),s._parsed||(a[r].push(s),s.endTime-n<.25&&(s.endTime=n+.25),s._parsed=!0)}}for(let e=0;e<a.length;e++)a[e].length&&a[e].forEach((e=>{const t=S(e);this.trigger(l.O1,t)}))},triggerActiveCues(e,t,s){const i=e[0];if(null!=i&&i.track&&"showing"===i.track.mode){const{kind:e,label:t,language:a,mode:r,activeCues:n}=i.track,{_id:d}=s;this.trigger(l.zs,{id:d,kind:e,label:t,language:a,mode:r,activeCues:n?Array.from(n):null})}const a=e.filter((e=>{if(null!=t&&t.some((t=>C(e,t))))return!1;if(e.data)return!0;const s=e.text?(e=>{let t;try{t=JSON.parse(e.text)}catch(e){return null}const s={metadataType:t.metadataType,metadataTime:e.startTime,metadata:t};return t.programDateTime&&(s.programDateTime=t.programDateTime),s})(e):null;if(s)"emsg"===s.metadataType&&(s.metadata=s.metadata||{},s.metadata.messageData=e.value),this.trigger(l.rx,s);else if(e.value)return!0;return!1}));a.length&&a.forEach((e=>{const t=S(e);this.trigger(l.rx,t)}))},ensureMetaTracksActive(){const e=this.video.textTracks,t=e.length;for(let s=0;s<t;s++){const t=e[s];"metadata"===t.kind&&"disabled"===t.mode&&(t.mode="hidden")}},_cacheVTTCue(e,t,s){const i=e.kind,a=e._id,r=this._cachedVTTCues;r[a]||(r[a]={});const n=r[a];let d;switch(i){case"captions":case"subtitles":{d=s||Math.floor(20*t.startTime);const e=`_${t.line||"auto"}`,i=Math.floor(20*t.endTime),a=n[d+e]||n[d+1+e]||n[d-1+e];return!(a&&Math.abs(a-i)<=1)&&(n[d+e]=i,!0)}case"metadata":{const e=t.data?new Uint8Array(t.data).join(""):t.text;return d=s||t.startTime+e,n[d]?!1:(n[d]=t.endTime,!0)}default:return!1}},_addTrackToList(e){this._textTracks.push(e),this._tracksById[e._id]=e},_createTrack(e){let t;const s=(0,a._)(e,this._unknownCount),i=s.label;if(this._unknownCount=s.unknownCount,this.renderNatively||"metadata"===e.kind){const s=this.video.textTracks;t=(0,h._e)(s,{label:i}),t||(t=this.video.addTextTrack(e.kind,i,e.language||"")),t.default=e.default,t.mode="disabled",t.inuse=!0}else t=e,t.data=t.data||[];return t._id||(t._id=(0,a.M)(e,this._textTracks?this._textTracks.length:0)),t},_clearSideloadedTextTracks(){if(!this._textTracks)return;const e=this._textTracks.filter((e=>e.embedded||"subs"===e.groupid));this._initTextTracks();const t=this._tracksById;e.forEach((e=>{t[e._id]=e})),this._textTracks=e}}},5016:(e,t,s)=>{s.r(t),s.d(t,{default:()=>p});var i=s(1643),a=s(328),r=s(6042),n=s(4446);const d=class{constructor(e,t){this.chrome=t?t.chrome:window.chrome,this.cast=t?t.chrome.cast:this.chrome.cast,this.Media=t?t.chrome.cast.media:this.cast.media,this.framework=t?t.cast.framework:window.cast.framework,this.context=t?t.cast.framework.context:this.framework.CastContext.getInstance(),this.castSession=t?t.cast.framework.castSession:null,this.CAST_STATE_CHANGED=this.framework.CastContextEventType.CAST_STATE_CHANGED||null,this.appId=e||this.Media.DEFAULT_MEDIA_RECEIVER_APP_ID,this.loaded=this.loaded.bind(this),this.updateCastState=this.updateCastState.bind(this),this.queueLoaded=this.queueLoaded.bind(this),this.queueErrored=this.queueErrored.bind(this),this.mediaAdded=this.mediaAdded.bind(this),this.mediaUpdate=this.mediaUpdate.bind(this)}init(){Object.assign(this,a.ZP),this.context.removeEventListener(this.CAST_STATE_CHANGED,this.updateCastState),this.context.addEventListener(this.CAST_STATE_CHANGED,this.updateCastState),this.context.setOptions({receiverApplicationId:this.appId,autoJoinPolicy:this.cast.AutoJoinPolicy.ORIGIN_SCOPED})}requestCast(e){this.trigger("castRequested",e)}checkDuration(e,t){return(null==e?void 0:e.duration)>0||(e.duration=t.mediaModel.get("duration")||null),e}async setPlaylist(e){var t;const s=e.get("playlist");let a=e.get("item"),r=e.mediaModel.get("currentTime");const d=e.get("repeat"),o=e.get("captions"),c=(null==(t=this.castSession)?void 0:t.getSessionObj())||await this.requestSession();if(!c)return;let l=s[a];if("complete"===e.get("state")&&(a=0,r=0),1!==s.length||e.get("related")){const t=[];let l=1,h=0;1===s.length&&e.get("related")&&e.get("recItems")&&e.get("recItems").length&&s.push(...e.get("recItems"));for(let i=a;i<s.length;i++){let n=s[i];n=this.checkDuration(n,e);const d=this.getMediaInfo(n,i,o);let c;if(d){c=new this.Media.QueueItem(d),d.metadata.index===a&&(c.startTime=r,h=t.length);const e=JSON.stringify(c).length+1;if(!(l+e<32e3))break;t.push(c),l+=e}}if(t.length){const e=new this.Media.QueueLoadRequest(t);e.startIndex=h,d&&(e.repeatMode=this.Media.RepeatMode.ALL),c.queueLoad(e,this.queueLoaded,this.queueErrored)}else this.trigger(i.cM,new n.rG(null,35e4,{info:"media not supported by Chromecast"}))}else{l=this.checkDuration(l,e);const t=this.getMediaInfo(l,a,o),s=new this.Media.LoadRequest(t);s.autoplay=!0,s.currentTime=r,c.loadMedia(s,this.loaded,this.error)}}requestSession(){return this.context.requestSession().then((e=>e)).catch((e=>null))}queueLoaded(e){this.loaded(e)}queueErrored(e){this.error(e)}getPlayerId(){const e=this.getMedia();let t,s;return null!=e&&e.media?(t=e.media.metadata,t.playerId):this.castSession?(s=this.castSession.getSessionObj(),s.playerId):null}setPlayerId(e){if(!this.castSession)return;this.castSession.getSessionObj().playerId=e}loaded(e){this.trigger("mediaUpdate",{field:"volume",value:{volume:this.castSession.getVolume(),isMute:this.castSession.isMute()}}),this.mediaAdded(e),this.play()}addListeners(){if(!this.castSession)return null;const e=this.castSession.getSessionObj();e.removeUpdateListener(this.updateCastState),e.addUpdateListener(this.updateCastState),e.removeMediaListener(this.mediaAdded),e.addMediaListener(this.mediaAdded),this.castSession.addEventListener(this.framework.SessionEventType.VOLUME_CHANGED,(e=>{this.trigger("mediaUpdate",{field:"volume",value:e})}))}reset(){this.removeListeners(),this.context&&this.context.removeEventListener(this.CAST_STATE_CHANGED,this.updateCastState)}removeListeners(){if(!this.castSession)return;const e=this.castSession.getSessionObj();e.removeUpdateListener(this.updateCastState),e.media.forEach((e=>{e.removeUpdateListener(this.mediaUpdate)})),this.castSession.removeEventListener(this.framework.SessionEventType.VOLUME_CHANGED)}getMedia(){if(this.castSession){const e=this.castSession.getSessionObj().media;if(null!=e&&e.length)return e[0]}return null}error(e){this.trigger(i.cM,new n.rG(null,35e4,{errorCode:e})),this.disconnect()}item(e){const t=this.getMedia();if(!t)return void this.trigger("setPlaylist");const s=this.getMediaInfo(e),i=(0,r.sE)(t.items,(function(e){return e.media.contentId===s.contentId&&e.media.index===s.index}));i?t.queueJumpToItem(i.itemId):this.trigger("setPlaylist")}play(){const e=this.getMedia();e&&e.play()}pause(){const e=this.getMedia();e&&e.pause()}next(){const e=this.getMedia();e&&e.queueNext()}disconnect(){this.castSession&&this.castSession.endSession(!0)}seek(e,t){const s=this.getMedia();if(s){const i=new this.Media.SeekRequest;i.currentTime=e,i.resumeState=this.Media.ResumeState.PLAYBACK_START,s.seek(i,t)}}mute(e){this.castSession&&this.castSession.setMute(e)}volume(e){this.castSession&&!this.castSession.isMute()&&this.castSession.setVolume(e/100)}editTracksInfo(e,t){const s=this.getMedia();if(s){const i=new this.Media.EditTracksInfoRequest(e,t);s.editTracksInfo(i)}}extractEmbeddedCaptions(){const e=this.getMedia();if(!e||!e.media.tracks)return;const t=/\.dfxp/,s=e.media.tracks.filter((e=>"TEXT"===e.type&&"side-loaded captions"!==e.customData&&!t.test(e.trackContentId))).map(((e,t)=>(e.mapId=t,e.kind="subtitles",e.cues=[],e)));s.length&&this.trigger("mediaUpdate",{field:"captions",value:{tracks:s}})}getMediaInfo(e,t,s){var i;let a=e.sources;e.allSources&&(a=e.allSources.slice(0).sort((function(e,t){return!e.default&&t.default?1:0})));const n=(0,r.sE)(a,(function(e){const t=!(0,r.dp)(e.mediaTypes)||!(0,r.r3)(e.mediaTypes,'video/webm; codecs="vp9"'),s=!(0,r.dp)(e.drm)||(0,r.Yj)(e.drm,(function(e,t){return"fairplay"!==t}));return t&&s}));if(!n)return;const d=this.getMimeType(n.type),o=this.getAbsolutePathWithProtocol(n.file),c=e.image?this.getAbsolutePathWithProtocol(e.image):null,l=n.drm,h=e.duration?e.duration:null,u=new this.Media.MediaInfo(o,d);var m,T;return u.streamType=!h||h<0||h===1/0?"LIVE":"BUFFERED",u.metadata=new this.Media.GenericMediaMetadata,u.metadata.title=e.title,u.metadata.subtitle=e.description,u.metadata.index=t||0,u.metadata.playerId=this.getPlayerId(),null!=e&&null!=(i=e.tracks)&&i.length&&(u.tracks=(m=e.tracks,T=this.Media,m.filter((e=>e.kind&&Boolean(T.TextTrackType[e.kind.toUpperCase()]))).map(((e,t)=>{const s=t+1,i=new T.Track(s,T.TrackType.TEXT);i.trackContentId=e.file,i.trackContentType="text/vtt",i.name=e.label||s;const a=i.subtype=T.TextTrackType[e.kind.toUpperCase()];return a!==T.TextTrackType.CAPTIONS&&a!==T.TextTrackType.SUBTITLES&&a!==T.TextTrackType.DESCRIPTION||(i.customData="side-loaded captions",i.language="en-US"),i})))),s&&(u.textTrackStyle=this.obtainTrackStyles(s)),c&&(u.metadata.images=[{url:c}]),l&&(u.customData={drm:l}),u}obtainTrackStyles(e){const t=function(e){return Math.round(e/100*255).toString(16)},s=new this.Media.TextTrackStyle,i=(e,t)=>e&&e+t||void 0;return s.foregroundColor=i(e.color,t(e.fontOpacity)),s.backgroundColor=i(e.backgroundColor,t(e.backgroundOpacity)),s.windowColor=i(e.windowColor,t(e.windowOpacity)),s.fontFamily=e.fontFamily,s.fontStyle=this.Media.TextTrackFontStyle.NORMAL,s.fontScale=e.fontSize/14,s.edgeType=function(e,t){const s=t.TextTrackEdgeType;switch(e){case"dropShadow":return s.DROP_SHADOW;case"raised":return s.RAISED;case"depressed":return s.DEPRESSED;case"uniform":return s.OUTLINE;default:return s.NONE}}(e.edgeStyle,this.Media),s.windowType=this.Media.TextTrackWindowType.NORMAL,s}getAbsolutePathWithProtocol(e){const t=document.createElement("a");return t.href=e,t.href}getMimeType(e){switch(e){case"mp4":case"webm":return`video/${e}`;case"mpd":case"dash":return"application/dash+xml";case"m3u8":case"hls":return"application/x-mpegURL";case"aac":return"audio/x-aac";case"mp3":return"audio/mpeg";default:return e}}updateCastState(){const e=this.context.getCastState()!==this.framework.CastState.NO_DEVICES_AVAILABLE;let t="";this.castSession=this.context.getCurrentSession(),this.castSession&&(t=this.castSession.getCastDevice().friendlyName||t),this.trigger("castState",{available:e,active:Boolean(this.castSession),deviceName:t})}mediaUpdate(){const e=this.getMedia();e&&this.trigger("mediaUpdate",{field:"media",value:e})}mediaAdded(e){e.removeUpdateListener(this.mediaUpdate),e.addUpdateListener(this.mediaUpdate)}};var o=s(2799),c=s(686),l=s(6528),h=s(3328);class u{}Object.assign(u.prototype,l.Z,a.ZP,h.Z,{getName:()=>({name:"chromecast"}),getQualityLevels:(0,r.a9)(["Auto"])});const m=class extends u{constructor(e,t){super(),this.playerId=e,this.playerConfig=t,this.minDvrWindow=t.minDvrWindow,this.backgroundImage=null}castEventHandlers(e){const t={media:e=>{const s=this.getRemote("items"),a="IDLE"===e.playerState&&"FINISHED"===e.idleReason,r="IDLE"===e.playerState&&"ERROR"===e.idleReason,d=a&&!s;t.playerState(d?"complete":e.playerState),t.currentTime(),clearInterval(this.timeInterval),"PLAYING"===e.playerState?this.timeInterval=setInterval(t.currentTime,100):a?this.setState("itemComplete"):d?this.setState("complete"):r&&(this.setState("error"),this.trigger(i.cM,new n.rG(null,35e4,e)),s||this.castService.disconnect())},volume:e=>{this.trigger("volume",{volume:Math.round(100*e.volume)}),this.trigger("mute",{mute:e.isMute})},captions:e=>{this.clearTracks(),this.setTextTracks(e.tracks),this.trigger("subtitlesTracks",{tracks:e.tracks})},playerState:e=>{const t=[i.Kb,i.bc,i.r0,i._5,i.nQ,i.ik,i.xQ,i.Vy];if(!e||-1===t.indexOf(e.toLowerCase()))return;const s=e.toLowerCase();if(s===i.bc||s===i.Kb){const e=this.getRemote("currentTime");(0,r.hj)(e)&&this.trigger(i.uT,{bufferPercent:0,position:this.getPosition(),duration:this.getDuration(),currentTime:e,seekRange:this.getSeekRange()})}this.setState(s)},currentTime:this.triggerTime.bind(this),duration:this.triggerTime.bind(this),isPaused:e=>{e?this.setState(i._5):this.setState(i.r0)},supports:()=>!0};return t[e]?t[e]:null}destroy(){clearInterval(this.timeInterval)}setService(e){this.castService=e,this.updateScreen()}setup(e){this.setState(i.Kb),this.sendCommand("setup",e)}init(e){this.currentItem!==e&&(this.currentItem=e,this.sendCommand("item",e))}load(e){this.init(e),this.play()}play(){this.sendCommand("play")}pause(){this.sendCommand("pause")}seek(e){const t=this.getRemote("currentTime");if(this.trigger(i.NZ,{position:this.getPosition(),offset:e,duration:this.getDuration(),currentTime:t,seekRange:this.getSeekRange(),metadata:{currentTime:t}}),e<0){const{end:t}=this.getSeekRange();e+=t}this.sendCommand("seek",e,(()=>{this.trigger(i.aQ)}))}next(e){this.sendCommand("next",e)}volume(e){this.sendCommand("volume",e)}mute(e){this.sendCommand("mute",e)}setSubtitlesTrack(e){const t=e>0?[e+this.minimumEmbeddedTrackId()]:[];this.castService.editTracksInfo(t)}minimumEmbeddedTrackId(){const e=window.chrome.cast.media.TextTrackType;e.CAPTION="CAPTION",e.SUBTITLE="SUBTITLE";const t=this.castService.getMedia();let s=0;if(!t)return s;const i=t.media.tracks;if(!i)return s;for(let t=0;t<i.length;t++){const a=i[t],r=a.subtype;if("TEXT"===a.type&&(r===e.CAPTIONS||r===e.SUBTITLES||r===e.DESCRIPTIONS||r===e.CAPTION||r===e.SUBTITLE||"text/vtt"===a.trackContentType)){s=t;break}}return s}sendCommand(e,...t){this.castService&&this.castService[e]&&this.castService[e](...t)}getRemote(e){if(!this.castService)return;const t=this.castService.getMedia();return t?"currentTime"!==e||t.liveSeekableRange?t[e]||(t.media?t.media[e]:null):t.getEstimatedTime():null}updateScreen(e,t){this.backgroundImage===t&&this.statusMessage===e||(this.backgroundImage=t,this.statusMessage=e,(0,o.nh)(this.container,((e,t)=>`<div class="jw-cast jw-reset jw-preview" style="${t?`background-image:url('${t}')`:""}">\n      <div class="jw-cast-container">\n        <div class="jw-cast-text jw-reset">\n          ${e||""}\n        </div>\n      </div>\n    </div>`)(this.statusMessage,this.backgroundImage)))}getContainer(){return this.container}setContainer(e){this.container=e}remove(){this.statusMessage=null,clearInterval(this.timeInterval)}getPosition(){const e=this.getRemote("currentTime")||0,t=this.getDuration();if(this.getRemote("liveSeekableRange")&&t<0){const{end:t,start:s}=this.getSeekRange(),i=t-s;if((0,c.s)(i,this.minDvrWindow))return e-t}return e}getDuration(){const e=this.getRemote("duration")||0;if(this.getRemote("liveSeekableRange")&&e<0){const{end:e,start:t}=this.getSeekRange(),s=e-t;return(0,c.s)(s,this.minDvrWindow)?-s:1/0}return e}getSeekRange(){const{start:e,end:t}=this.getRemote("liveSeekableRange")||{start:0,end:Math.max(this.getRemote("duration")||0,0)};return{start:e,end:t}}triggerTime(){const e=this.getRemote("currentTime");(0,r.hj)(e)&&this.trigger(i.R2,{position:this.getPosition(),duration:this.getDuration(),currentTime:e,seekRange:this.getSeekRange(),metadata:{currentTime:e}})}stop(){this.clearTracks()}};var T=s(676);let g;var k=s(8494);const v={};const p=class{constructor(e,t,s){this.stopCasting=()=>{var e;return(null==this||null==(e=this.service)||null==e.disconnect?void 0:e.disconnect())||k.Z.noop},this.localController=e,this.model=t,this.service=v[this.model.get("id")]||null,this.castProvider=null,this.castToggle=k.Z.noop,this.setup=this.setup.bind(this),this.options=s||{},this.loadingApi=g||(g=new Promise((function(e,t){window.__onGCastApiAvailable=function(s){s?e(s):t(),delete window.__onGCastApiAvailable},new T.ZP("https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1").load().catch(t)})),g)}init(){return this.loadingApi.then(this.setup)}setup(){const e=this.model.get("cast")||{};null!=e&&e.interceptCast&&this.model.set("interceptCast",!0),this.model.set("castState",{available:!1,active:!1,deviceName:""}),this.service&&(this.service.off(),this.service.reset());const t=this.options&&(this.options.CastService||d);this.service=new t(e.appid||e.customAppId),this.service.init(),this.service.on("castState",this.updateCastState,this),this.service.on("mediaUpdate",this.onMediaUpdate,this),this.service.on("mediaUpdate",this.onFirstMediaUpdate,this),this.service.on("setPlaylist",this.setPlaylist,this),this.service.on("castRequested",this.updateCastItem,this),this.service.on(i.cM,(e=>{this.localController.trigger(i.cM,e)})),this.service.updateCastState(),v[this.model.get("id")]=this.service}switchProviders(){const e=this.options&&(this.options.CastProvider||m);this.castProvider=new e(this.model.get("id"),this.model.getConfiguration()),this.localController.castVideo(this.castProvider,this.model.get("playlistItem")),this.castProvider.setService(this.service)}setPlaylist(){this.model.set("state",i.Kb),this.castProvider.updateScreen("Connecting",this.model.get("playlistItem").image),this.service.setPlaylist(this.model)}onConnect(){var e;const t=this.model.get("castClicked");if((t||!this.service.getPlayerId())&&this.service.setPlayerId(this.model.get("id")),!t||!this.isActivePlayer())return;const s=null==(e=this.model.getVideo())?void 0:e.video;null==s||s.removeAttribute("disableRemotePlayback"),this.localController.setFullscreen(!1),this.switchProviders(),this.service.addListeners();const i=this.service.getMedia();i?this.service.loaded(i):(this.service.on("mediaUpdate",this.seekToEdgeIfDvr,this),this.setPlaylist()),this.model.on("change:playlist",this.setPlaylist,this),this.model.on("change:itemReady",this.checkForEmbeddedCaptions,this),this.model.change("captions",this.updateCaptionStyles,this)}onDisconnect(){const e=this.model.get("state");let t=e===i.xQ;const s=e===i.bc,a=e===i.Vy,r=this.model.get("item"),n=this.model.get("playlist");let d=this.model.get("playlistItem");if(this.service.removeListeners(),this.castProvider&&this.castProvider.remove(),d&&a&&(d=n[r+1],void 0===d?t=!0:(this.model.set("item",r+1),this.model.set("playlistItem",d))),this.model.set("castActive",!1),this.model.set("castClicked",!1),this.localController.stopCast(),this.model.off(null,null,this),d)if(t)this.localController.trigger(i.V$,{});else if(!s){const e=this.model.mediaModel,t=this.castProvider;this.localController.playVideo("interaction").catch((function(s){t&&e&&t.trigger("error",{message:s.message})}))}}toggleConnection(e){e?this.onConnect():this.castProvider&&this.onDisconnect()}checkForEmbeddedCaptions(){this.service.extractEmbeddedCaptions(),this.castProvider.setSubtitlesTrack(this.model.get("captionsIndex"))}updateCaptionStyles(e,t){const s=this.service.getMedia();if(!s)return;const i=this.service.obtainTrackStyles(t);this.service.editTracksInfo(s.activeTrackIds,i)}onMediaUpdate(e){const t=e.field,s=e.value;if(!this.castProvider)return;"media"===t&&this.updatePlaylistItem(s);const i=this.castProvider.castEventHandlers(t);i&&i(s)}onFirstMediaUpdate(e){"media"===e.field&&(this.checkForEmbeddedCaptions(),this.service.off("mediaUpdate",this.onFirstMediaUpdate,this))}seekToEdgeIfDvr(e){if("media"!==e.field)return;this.service.off("mediaUpdate",this.seekToEdgeIfDvr,this);const t=e.value,{currentTime:s,liveSeekableRange:i}=t;if(!s&&i){const{start:e,end:t}=i;if(!this.model.mediaModel.get("currentTime")&&(0,c.s)(t-e,this.model.get("minDvrWindow"))){const e=t-this.model.get("dvrSeekLimit");this.service.seek(e)}}}updatePlaylistItem(e){const t=this.model.get("playlist");if(!e.media)return;const s=e.media.metadata,i=t[s.index],a=this.model.get("castState").deviceName,n=a?`Casting to ${a}`:"";this.castProvider.updateScreen(n,i.image),(0,r.hj)(s.index)&&s.index!==this.model.get("item")&&(this.model.attributes.itemReady=!1,this.model.set("item",s.index),this.model.set("itemReady",!0),e.idleReason||this.model.set("playlistItem",i),"itemComplete"===this.castProvider.state&&this.model.get("playlistItemCallback")&&this.castProvider.sendCommand("item",i))}updateCastState(e){const t=this.model.get("castActive");let s=e.active;t!==s&&this.toggleConnection(s),s=s&&this.isActivePlayer(),this.model.set("castAvailable",e.available),this.model.set("castActive",s),this.model.set("castState",{available:e.available,active:s,deviceName:e.deviceName})}isActivePlayer(){return this.service.getPlayerId()===this.model.get("id")}updateCastItem(e){this.model.set("playlist",e),this.model.set("playlistItem",e[0]),this.localController.setPlaylistItem(0,this.model.get("playlistItem")),this.setPlaylist()}}}}]);
var Search = {
  // when showing search detail show view, need to also trigger a manual search
  //   of captions using same search terms
  propogateTextSearchToCaptions: function() {
    // do not propogate if highlight term is off
    const highlightState = PathHelpers.getParamValue(window.location.href, 'highlight');
    if (highlightState == 'off') { return };


    // search terms should already be filled into form search field by server side rendering of form
    const searchSubmitBtn = document.getElementById('search_submit');
    searchSubmitBtn.click();
  },

  addListenerToToggleHighlightSearchTermsButton: function() {

    const clearBtn = document.getElementById('toggle-search-highlighting');
    let currentUrl = window.location.href;

    clearBtn.addEventListener('click', (e) => {
      Player.setPlayerStateInSession();
      const currentHighlightState = PathHelpers.getParamValue(currentUrl, 'highlight');
      let newUrl = null;

      if (currentHighlightState == 'on') {
        newUrl = PathHelpers.addParamsToQueryString(currentUrl, { 'highlight': 'off'} );
      } else {
        newUrl = PathHelpers.addParamsToQueryString(currentUrl, { 'highlight': 'on'} );
      }
      
      window.location = newUrl;
    });
  },

  addListenerToReturnToSearchResultsButton: function() {
    const backButton = document.getElementById('return_to_search_results');
    backButton.addEventListener('click', (e)=>{
      // back to search results index
      const currentUrl = window.location.href;
      const searchTerms = PathHelpers.getParamValue(currentUrl, 'terms');
      let newUrl = `${PathHelpers.playerBaseAbsUrl()}videos/search`;
      newUrl = PathHelpers.addParamsToQueryString(newUrl, { 'search': searchTerms });

      window.location = newUrl;
    });

  },

  addAjaxCallsForEachVideoForSearchMetadata: function() {
    const allVideos = document.querySelectorAll('div.video-item-container');

    allVideos.forEach(v => {
      const videoId = v.dataset.videoId;
      const videoType = v.dataset.videoType;
      const baseUrl = PathHelpers.playerBaseRelUrl(window.location.href);
      const searchTerms = PathHelpers.getParamValue(window.location.href, 'search');
      const csrfToken = document.querySelector("[name='csrf-token']").content;

      fetch(
        `${baseUrl}videos/search/${videoId}/metadata?vid_type=${videoType}&search=${searchTerms}`,
        { 
          method: 'GET',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }
        }
      ).then(response => {
        return response.json()
      }).then((data) => {
        const vidMetadataCountSpan = document.getElementById(`${videoType}${videoId}-video_metadata`);
        const captionLineCountSpan = document.getElementById(`${videoType}${videoId}-caption_lines`);
        const chapterMetadataCountSpan = document.getElementById(`${videoType}${videoId}-chapter_metadata`);
        const vidThumbImage = document.getElementById(`video_${videoType}_${videoId}`);

        if (data.video_metadata_count != '0') {
          vidMetadataCountSpan.innerHTML = `found ${data.video_metadata_count} time(s) in video metadata`;
        }

        if (data.caption_lines_count != '0') {
          captionLineCountSpan.innerHTML = `found ${data.caption_lines_count} time(s) in caption lines`;
        }
        
        if (data.chapters_metadata_count != '0') {
          chapterMetadataCountSpan.innerHTML = `found ${data.chapters_metadata_count} time(s) in chapters metadata`;
        }

        vidThumbImage.src = data.video_thumbnail_url;
        vidThumbImage.style.width = '100%';
        
      });
    });
  },

  addEventListenerToSearchSubmitButton: function() {
    const searchSubmitBtn = document.getElementById('search_submit_btn');

    if (searchSubmitBtn == null) {
      return;
    }

    searchSubmitBtn.addEventListener('click', (e) => {
      const btnContainer = document.getElementById('normally_visible');
      const spinnerLoadingImage = document.getElementById('spinner_loading_image');

      btnContainer.style.visibility = 'hidden';
      spinnerLoadingImage.style.display = 'block';

    });
  }
};


document.addEventListener("DOMContentLoaded", function(){
  let captionSidebar = document.querySelector('div#captions-text-container');
  const bodyClasses = document.querySelector('body').classList;

  if (bodyClasses.contains('searches-index')) {
    Search.addAjaxCallsForEachVideoForSearchMetadata();
  }


  if (bodyClasses.contains('searches-show')) {
    if (captionSidebar != null) {
      Search.propogateTextSearchToCaptions();
    }
    
    Search.addListenerToToggleHighlightSearchTermsButton();
    Search.addListenerToReturnToSearchResultsButton();
  }

  Search.addEventListenerToSearchSubmitButton();
});
var Series = {

};

document.addEventListener("DOMContentLoaded", function(){
  let cssClasses = document.querySelector('div#main').classList;
  if (cssClasses.contains('single-series')) {
    Videos.addClickHandlerToShowOrHideMoreControls();
  }
  
});
const StreamRetries = {
  reconnectConfig: {
    pollingSchedule: [
      { delayInMs: 10_000, attempts: 30 },
      { delayInMs: 60_000, attempts: 24 }
    ]
  },

  addListenerToRetryButton: function() {
    const retryButton = document.getElementById('stream_retry_button');

    if (!retryButton) return;

    retryButton.addEventListener('click', async function(e) {
      
      const spinner = document.getElementById('loading_spinner');
      const slateCountdown = document.getElementById('slate_countdown');
      retryButton.style.display = 'none';
      slateCountdown.style.display = 'none';
      spinner.style.display = 'inline-block';

      window.location.reload();
    });
  },

  validateStream: async function(streamId, url) {
    const csrfToken = document.querySelector('meta[name=csrf-token]').content;
    
    const resp = await fetch(url, {
      headers: { 'X-CSRF-Token': csrfToken, 'Accept': 'application/json' }
    });

    const data = await resp.json();
    return data.playable; 
  },

  automaticRetriesHandler: async function() {
    const buttonWithData = document.getElementById('stream_retry_button');
    if (!buttonWithData) return;

    const streamId = buttonWithData.dataset.streamId;
    const url = buttonWithData.dataset.url;

    for (const phase of StreamRetries.reconnectConfig.pollingSchedule) {
      for (let attempt = 1; attempt <= phase.attempts; attempt++) {
        // Countdown until next attempt
        await StreamRetries.delayWithCountdown(phase.delayInMs, StreamRetries.updateSlateSeconds);


        // remove button, messaging text and show spinner
        const retryButton = document.getElementById('stream_retry_button');
        const spinner = document.getElementById('loading_spinner');
        const slateCountdown = document.getElementById('slate_countdown');
        retryButton.style.display = 'none';
        slateCountdown.style.display = 'none';
        spinner.style.display = 'inline-block';


        try {
          const playable = await StreamRetries.validateStream(streamId, url);

          if (playable) {
            window.location.reload();
            return; // exit all loops
          }

          

        } catch (error) {
          console.error('Polling error:', error);
          
        }

        retryButton.style.display = 'inline-block';
        slateCountdown.style.display = 'block';
        spinner.style.display = 'none';
      }
    }

    // All retries exhausted
    const message = document.getElementById('slate_message');
    const countDown = document.getElementById('slate_countdown');
    if (countDown) countDown.style.display = 'none';
    if (message) message.innerHTML = 'Stream unavailable';
  },

  delayWithCountdown(totalMs, onTick) {
    return new Promise(resolve => {
      let remaining = Math.ceil(totalMs / 1000);

      // Initial paint
      onTick(remaining);

      const intervalId = setInterval(() => {
        remaining--;
        onTick(remaining);

        if (remaining <= 0) {
          clearInterval(intervalId);
        }
      }, 1000);

      setTimeout(() => {
        clearInterval(intervalId);
        resolve();
      }, totalMs);
    });
  },

  updateSlateSeconds: function(text) {
    const secondsDomElement = document.getElementById('slate_seconds');

    if (secondsDomElement) secondsDomElement.innerHTML = text;
  }


};




document.addEventListener("DOMContentLoaded", function(){
  const retryButton = document.getElementById('stream_retry_button');

  if (retryButton) {
    StreamRetries.addListenerToRetryButton();
    StreamRetries.automaticRetriesHandler();
  }
});
var Videos = {
  addEventHandlerForVideosOrderingSelects: function() {
    var sortBySelect = document.querySelector("select#sort_by");
    var orderBySelect = document.querySelector("select#order_by");
    var elementToReplace = document.querySelector(".video-rows-container");

    [sortBySelect, orderBySelect].forEach(select => {
      select.addEventListener("change", function(){
        let requestUrl = PathHelpers.addParamsToQueryString(
          window.location.href,
          { sort_by: sortBySelect.value, order_by: orderBySelect.value }
        );

        // clear existing rows, show loading spinner:
        elementToReplace.innerHTML = '<div class="video-rows-container"><span class="loading-spinner-container"></span></div>';

        fetch(requestUrl, { headers: { "Content-Type": "text/html; charset=utf-8" }})
          .then(res => res.text())
          .then(response => {
            elementToReplace.innerHTML = response;
            Videos.toggleLoadMoreButtonDisplay();
            Videos.addClickHandlerToShowOrHideMoreControls();
          })
          .catch(err => {
            console.log("error fetching video rows: " + err)
          });
      });
    });
  },

  // show the "Load more" button only if there are more videos to show
  toggleLoadMoreButtonDisplay: function() {
    let totalVideosCount = parseInt(document.querySelector(".video-rows-container").dataset.totalAvailableCount);

    let totalDisplayedCount = document.querySelectorAll(".video-item-container").length;
    let loadMoreContainer = document.querySelector("div.load-more-container");

    if (totalVideosCount > totalDisplayedCount) {
      loadMoreContainer.style.display = 'block';
    } else {
      loadMoreContainer.style.display = 'none';
    }
  },

  addClickHandlerToLoadMoreButton: function() {
    var loadMoreButton = document.querySelector("button.load-more");
    var elementToAddend = document.querySelector(".video-rows-container");
    var loadMoreButtonContainer = document.querySelector("span.load-more-button-container");
    var loadingSpinnerContainer = document.querySelector("span.loading-spinner-container");
    

    loadMoreButton.addEventListener("click", function(){
      let sortBySelect = document.querySelector("select#sort_by");
      let orderBySelect = document.querySelector("select#order_by");
      let totalDisplayedCount = document.querySelectorAll(".video-item-container").length;
      let requestUrl = PathHelpers.addParamsToQueryString(
        window.location.href,
        { sort_by: sortBySelect.value, order_by: orderBySelect.value, offset: totalDisplayedCount }
      );

      // hide the "load more" while loading, show spinner
      loadMoreButtonContainer.style.display = 'none';
      loadingSpinnerContainer.style.display = 'block';


      fetch(requestUrl, { headers: { "Content-Type": "text/html; charset=utf-8" }})
        .then(res => res.text())
        .then(response => {
          elementToAddend.innerHTML += response;
          
          Videos.addClickHandlerToShowOrHideMoreControls();
          // remove spinner, show "load more" button again if there are more rows to load
          loadingSpinnerContainer.style.display = 'none';
          loadMoreButtonContainer.style.display = 'block';
          Videos.toggleLoadMoreButtonDisplay();
          
        })
        .catch(err => {
          console.log("error fetching video rows")
        });
    });
  },

  addClickHandlerToShowOrHideMoreControls: function() {
    // These are link style controls
    let showOrHideMoreControls = document.querySelectorAll("button.show-attachments-link");
    showOrHideMoreControls.forEach(control => {
      control.addEventListener("click", function(event){
        event.preventDefault();
        let showOrHideTarget = $(this).siblings('div.summary')[0];

        if (showOrHideTarget.style.display == 'none' || showOrHideTarget.style.display == '') {
          $(showOrHideTarget).slideDown();
          this.innerHTML = 'Hide More';
        } else {
          $(showOrHideTarget).slideUp();
          this.innerHTML = 'Show More';
        }
      });
    });
  },

  addClickHandlerToShowOrHideChapterLinksAndAttachmentsControls: function() {
    // These are link style controls
    let showOrHideMoreControls = document.querySelectorAll(`[data-action*="show-or-hide-chapter-links-and-attachments"]`);

    showOrHideMoreControls.forEach(control => {
      control.addEventListener("click", function(event){
        event.preventDefault();

        let showOrHideTargets = this.closest('.details-container').querySelectorAll('.links-and-attachments-container');
        showOrHideTargets.forEach(targetElement => {
          if (targetElement.style.display == 'none') {
            $(targetElement).slideDown();
            this.innerHTML = 'Hide Attachments and Links';
          } else {
            $(targetElement).slideUp();
            this.innerHTML = 'Show Attachments and Links';
          }
        });
      });
    });
  },

  addClickHanderToChapterJumpControls: function() {
    let chapterControls = document.querySelectorAll('a.chapter-link');

    chapterControls.forEach(control => {
      control.addEventListener('click', function(event){
        event.preventDefault();
        let jumpToTime = this.dataset.start;
        jwplayer('jw_player_instance').seek(jumpToTime);
      });
    });
  },

  addClickHandlerToClearVideoSearchButton: function() {
    let clearVideoSearchBtn = document.querySelector('button.video-search-clear-btn');

    if (clearVideoSearchBtn != undefined) {
      clearVideoSearchBtn.addEventListener('click', function(event){
        event.preventDefault();
        window.location = PathHelpers.removeParamFromQueryString(window.location.href, 'search');
      });
    }
  
  }
};

document.addEventListener("DOMContentLoaded", function(){
  if (HelperFuncs.bodyHasClass(['videos-index'])) {
    let videoRowsContainer = document.querySelector(".video-item-container");
    if (videoRowsContainer != undefined) {
      Videos.addEventHandlerForVideosOrderingSelects();
      Videos.toggleLoadMoreButtonDisplay();
      Videos.addClickHandlerToLoadMoreButton();
    }
  }

  if (HelperFuncs.bodyHasClass(['videos', 'series-show', 'series-show_with_video', 'categories-show', 'categories-show_with_video'])) {
    Videos.addClickHandlerToShowOrHideMoreControls();
  }

  if (HelperFuncs.bodyHasClass(['videos-show', 'playlists-show_with_video', 'series-show_with_video', 'categories-show_with_video', 'searches-show'])) {
    Videos.addClickHandlerToShowOrHideChapterLinksAndAttachmentsControls();
    Videos.addClickHanderToChapterJumpControls();
  }

  if (HelperFuncs.bodyHasClass(['searches-index'])) {
    Videos.addClickHandlerToClearVideoSearchButton();
  }
  
});
