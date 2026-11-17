(function () {

    var url = $("#CheckLoadSearchItemsLink").val();
    if (url && url.length > 0) {
        $.ajax(url);
    }

    var SearchIndex, i_checks, arc, arco;
    $(function () {

        var SearchResults = $("#SearchResults");
        var q_searchbox = $("#q");
        i_checks = $("input[name=i]");
        arc = $("#arc");
        arco = $("#arco");

        var from = $("#from");
        var to = $("#to");

        if (window && window.History)
        {
            if (window.History.Adapter)
            {
                window.History.Adapter.bind(window, 'statechange', function () {
                    var State = window.History.getState();
                    if (State.data && State.data != null) {
                        SearchResults.html(State.data.HTML);
                        highlightElement(SearchResults);

                        q_searchbox.val(State.data.q);

                        i_checks.filter(":checked").prop('checked', false).change();
                        if (State.data.i != null && State.data.i.length > 0) {
                            $(State.data.i.split(',')).each(function (index, value) {
                                i_checks.filter("[value=" + value + "]").prop("checked", true).change();
                            });
                        }

                        from.val(State.data.from);
                        to.val(State.data.to);
                                              
                        if (State.data.arc != null && State.data.arc) {
                            SetArchivedCheckBox(arc, true);
                        }
                        else {
                            SetArchivedCheckBox(arc, false);
                        }                        
                        if (State.data.arco != null && State.data.arco) {
                            SetArchivedCheckBox(arco, true);
                        }
                        else {
                            SetArchivedCheckBox(arco, false);
                        }
                    }
                });
            }

            window.History.replaceState(getHistoryState(), document.title, "");
        }

        function SetArchivedCheckBox(element, checked) {
            element.prop('checked', checked).change();
        }

        SearchIndex = $("input[type=checkbox][name=i]");;

        $("#selectAllSearchIndex").click(function (event) {
            event.preventDefault();
            SearchIndex.each(function () {
                $(this).prop("checked", true).change();
            });
        });

        $("#selectNoneSearchIndex").click(function (event) {
            event.preventDefault();
            SearchIndex.each(function () {
                $(this).prop("checked", false).change();
            });
        });

        var searchInputForm = $("#searchInputForm");
        var searchSubmitButtons = searchInputForm.find("button[type=submit]");

        $("button.close.closeTab").click(function () {
            if (!window.confirm("Remove this constraint from the Search?"))
                return;
            $(this).closest("li").remove();
            searchInputForm.submit();
        });

        var AjaxSearchURL = $("#AjaxSearchURL").val();
        var SearchURL = $("#SearchURL").val();

        searchSubmitButtons.click(function (event) {
            event.preventDefault();

            searchSubmitButtons.each(function () {
                disEnable_Control(true, $(this));
            });

            SearchResults.html("<h3 class='advancedOptionsTitle search-spinner displayNone'><i class='fa fa-spinner fa-pulse'></i> Performing Search...</h3>");

            var search_spinners = $(".search-spinner");

            search_spinners.show("slow");

            var queryString = "?" + searchInputForm.serialize();

            var title = "Search";
            var addToTitle = q_searchbox.val();
            if (addToTitle.length > 0)
            {
                if (addToTitle.length > 40)
                {
                    addToTitle = addToTitle.substring(0, 30) + "...";
                }
                addToTitle = ": " + addToTitle;
            }

            $.get(AjaxSearchURL + queryString, function (data, textStatus, request) {
                if (request.getResponseHeader('Sparq_AjaxWasSuccessful') != '1') {
                    DisplayMessages().addErrorMsg('There was a problem performing this search. Please Try Again Later.', 5);
                    return;
                }
                SearchResults.html(data);
                highlightElement(SearchResults);

                
                window.History.pushState(getHistoryState(), title + addToTitle, SearchURL + queryString);
            })
            .always(function () {
                search_spinners.hide("slow", function () {
                    search_spinners.remove();
                });
                searchSubmitButtons.each(function () {
                    disEnable_Control(false, $(this));
                });
            });
        });

        function getHistoryState()
        {
            var i = getCheckedIndexes();
            return { HTML: SearchResults.html(), q: q_searchbox.val(), i: i, from: from.val(), to: to.val(), arc: arc.is(":checked"), arco: arco.is(":checked") };
        }

    });

    function getCheckedIndexes()
    {
        var response = "";
        i_checks.filter(":checked").each(function (index, value) {
            var _this = $(this);
            if (_this.is(":checked"))
            {
                if (response.length > 0)
                    response += ",";
                response += _this.val();
            }
        });

        return response;
    }    
}())
