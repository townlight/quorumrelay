(function (g) {
    var $ = gQuery; // use jquery as $ in localized anonymous function scope

    var default_options = {
        selector: '#pagination',
        onPageClick: $.noop()
    };

    //  
    /*  running >> granicus.module.pagination(opts) <<
    anywhere else in the application creates a pagination object with no pages (default)
    -----------------------------------------------*/
    g.module.pagination = function (options) {
        return new Pagination(options);
    };

    function Pagination(options) {

        /*  set default variables & object properties
        -----------------------------------------------*/
        var opts = $.extend({}, default_options, options),
            selector = this.sel = opts.selector, // class property >> this.sel << is being set
            onPageClick = this.onPageClick = opts.onPageClick,
            self = this;

        /*  Private Method - initHtml
        Creates the UI container for pagination
        -----------------------------------------------*/
        function initHtml() {
            var html = '<div class="gpg_wrap"><a class="gpg_left gpg_off" aria-live="polite">&laquo; Previous</a><div class="gpg_pages"></div><a class="gpg_right gpg_off" aria-live="polite">Next &raquo;</a></div>';

            $(selector).html(html);

            // gaurantee event binding to occur after html() paint
            setTimeout(function () {

                // use of $.delegate allows us to add and remove HTML without re-binding elements
                // $.live is an alternative option with the 'context' option (same performance) if using older version of jQuery
                // .delegate works for jQuery / gQuery 1.4+ only...

                $(selector + ' .gpg_pages').delegate('a', 'click', function (e) {
                    var page = $(this).text();
                    if (page === '...') return;
                    self.load(parseInt(page), self.total_pages);
                });

                $(selector + ' .gpg_left').bind('click', function () {
                    if ($(this).hasClass('gpg_off')) return;
                    self.load(self.current_page - 1, self.total_pages);
                });
                $(selector + ' .gpg_right').bind('click', function () {
                    if ($(this).hasClass('gpg_off')) return;
                    self.load(self.current_page + 1, self.total_pages);
                });

            }, 1);
        }

        /*  Run initialization code
        -----------------------------------------------*/
        initHtml();

        this.hide = function () {
            $(selector).css({ display: 'none' });
        };
        this.show = function () {
            $(selector).css({ display: 'block' });
        };
        this.first_load = true;
    }

    /*  Public Method - load
    creates the pages
    event delegation was already done in private method "initHtml()"
    -----------------------------------------------*/
    Pagination.prototype.load = function (page, total) {
        var pages = [],
            longer = total > 9,
            bridge_left = longer && page > 4,
            bridge_right = longer && page <= (total - 4),
            sel = this.sel,
            prev_link = $(this.sel + ' .gpg_left').addClass('gpg_off').attr("aria-disabled", "true"),
            next_link = $(this.sel + ' .gpg_right').addClass('gpg_off').attr("aria-disabled", "true"),
            self = this;

        self.setWidth(total); // modify length based on # of digits

        self.current_page = page;
        self.total_pages = total;

        for (var i = 1; i <= total; i++) {
            pages.push(i);
        }

        // if greater than than 4
        if (bridge_left) {
            var offset = bridge_right ? 3 : 3 + (4 - (total - page));
            pages.splice(0, (page - offset));
            pages = [1, '...'].concat(pages);
        }

        // if 4 from end
        if (bridge_right) {
            var offset = bridge_left ? 3 : 8 - page;
            var index = pages.indexOf(page) + offset;
            pages.splice(index, total);
            pages = pages.concat(['...', total]);
        }

        var len = pages.length,
            html = [];
        for (var i = 0; i < len; i++) {
            var p = pages[i];
            if (p === '...') {
                html.push('<a class="gpg_bridge">...</a>');
            } else if (p === page) {
                html.push('<a class="gpg_on" aria-current="page" aria-label="Current Page, Page ' + p + '">' + p + '</a>');
            } else {
                html.push('<a aria-label="Page ' + p + '">' + p + '</a>');
            }
        }
        $(sel + ' .gpg_pages').html(html.join(''));

        // prev & next buttons off/on
        setTimeout(function () {
            if (page !== 1) prev_link.removeClass('gpg_off');
            if (page !== total) next_link.removeClass('gpg_off');
            if (self.first_load) {
                self.first_load = false;
            } else {
                self.onPageClick(page);
            }
        }, 1);
        this.show();
    }

    Pagination.prototype.setWidth = function (total) {
        var extra_digits = (total + '').length - 2,
			base_width = total < 10 ? total * 100 / 2 + 200 : 500,
			width = 50 * extra_digits + base_width;
        $(this.sel + ' .gpg_wrap').width(width);
    }


    if (!Array.indexOf) {
        Array.prototype.indexOf = function (obj, start) {
            for (var i = (start || 0); i < this.length; i++) {
                if (this[i] == obj) {
                    return i;
                }
            }
            return -1;
        }
    }
})(granicus);