$(window).ready(function() {
    $('.select2').select2({theme: 'bootstrap', width: "100%"});
    if($("#locust_count").length > 0) {
        $("#locust_count").focus().select();
    }
});

$("#box_stop a.stop-button").click(function(event) {
    event.preventDefault();
    $.get($(this).attr("href"));
    $("body").attr("class", "stopped");
    $(".box_stop").hide();
    $("a.new_test").show();
    $("a.edit_test").hide();
    $(".user_count").hide();
});

$("#box_stop a.reset-button").click(function(event) {
    event.preventDefault();
    $.get($(this).attr("href"));
});

$(".ramp_test").click(function(event) {
    event.preventDefault();
    $("#start").hide();
    $("#ramp").show();
    $("#edit_config").hide();
    $(".status").removeClass("none");
});

$("#new_test").click(function(event) {
    event.preventDefault();
    $("#start").show();
    $("#ramp").hide();
    $("#edit_config").hide();
    $("#locust_count").focus().select();
    $(".status").removeClass("none");
});

$(".edit_test").click(function(event) {
    event.preventDefault();
    $("#edit").show();
    $("#new_locust_count").focus().select();
});

$(".back_new_test").click(function(event) {
    event.preventDefault();
    $("#start").show();
    $("#ramp").hide();
    $("#edit_config").hide();
    $("#locust_count").focus().select();
    $(".status").removeClass("none");
});

$(".close_link").click(function(event) {
    event.preventDefault();
    $(this).parent().parent().hide();
});

var chartFilters = ['users','rps','response time','failures']
$(".chart-filter > button").click(function(event) {
    let activeFilters = advanceChart.getActiveFilter()
    if(!!advanceChart) {
        if(!activeFilters.includes($(this).index())) {
            if(activeFilters.length < 2) {
                advanceChart.addFilter($(this).index())
                $(this).removeClass("btn-outline-secondary")
                $(this).addClass("btn-secondary")
            }
        } else {
            if(activeFilters.length > 1) {
                advanceChart.removeFilter($(this).index())
                $(this).removeClass("btn-secondary")
                $(this).addClass("btn-outline-secondary")
            }
        }
    }
})

$('#ramp_form').submit(function(event) {
    event.preventDefault();
    $.post($(this).attr("action"), $(this).serialize(),
        function(response) {
            if (response.success) {
                $("body").attr("class", "hatching");
                $("#ramp").fadeOut();
                $("#status").fadeIn();
                $(".box_running").fadeIn();
                $("a.new_test").fadeOut();
                $("a.edit_test").fadeIn();
                $(".user_count").fadeIn();
                resetCharts();
            }
        }
    );
});

$('.close_link_headers').click(function(event) {
    event.preventDefault();
    $("#column_header").empty();
    $(this).parent().parent().hide();
});

var alternate = false;

$("ul.tabs").tabs("div.panes > div").on("onClick", function(event) {
    if (event.target == $(".chart-tab-link")[0]) {
        // trigger resizing of charts
        if (!!rpsChart) rpsChart.resize()
        if (!!responseTimeChart) responseTimeChart.resize()
        if (!!usersChart) usersChart.resize()
        if (!!failureChart) failureChart.resize()
        if (!!endpointResponseTimeCharts) {
          for (var chartKey in endpointResponseTimeCharts) {
            endpointResponseTimeCharts[chartKey].resize()
            endpointRpsCharts[chartKey].resize()
            endpointFailureCharts[chartKey].resize()
          }
        }
    }
});

$("ul.tabs_json").tabs("div.panes_json > div");


/*** START OF JSON EDITOR'S ***/

$(".edit_config_link").click(function(event) {
    event.preventDefault();

    var simple_json_container = document.getElementById("simple_json_editor");
    var options = {
        mode: 'tree',
        modes: ['code', 'tree'],
        onChange: function(element,event){
            $("#hidden_config_json").val(JSON.stringify(simple_json_editor.get(), null , 4));
            $("#multiple_hidden_config_json").val(JSON.stringify(simple_json_editor.get(), null , 4));
        },
        onError: function (err) {
            alert(err.toString());
          }
    }
    var simple_json_editor = new JSONEditor(simple_json_container, options);
    simple_json_editor.set(JSON.parse($("#hidden_config_json").val()));
    

    $("#start").hide();
    $("#ramp").hide();
    $("#edit_config").show();
    $(".status").addClass("none");
    $("#config_tab").trigger("click");
});

$('#simple_config_form').submit(function(event) {
    event.preventDefault();
    $.post($(this).attr("action"), $(this).serialize(),
        function(response) {
            if (response.success) {
                location.reload(true);
            }
        }
    );
});

$('#upload_csv_btn').click(function(event) {
    event.preventDefault();
    var form = $('#upload_csv')[0];
    var form_data = new FormData(form);
    $.ajax({
        type: 'POST',
        url: "/config/get_csv_column",
        enctype: 'multipart/form-data',
        data: form_data,
        contentType: false,
        cache: false,
        processData: false,
        success: function (response) {
            if (response.success) {
                $(".multiple_column").show();
                $(this).parent().remove();
                var rownum = 0;
                if(response.columns.length > 1)
                {
                    $.each(response.columns, function (key, value) {
                        rownum++;
                        var li = $('<li><label><input type="checkbox" id="headers_checkbox'+rownum+'" name="headers_checkbox" value="' + value + '">'+value+'</label>');
                        $('#column_header').append(li);
                        $('#headers_checkbox'+rownum).on('click', function(){
                            if($(this).is(":checked")) {
                                $(this).prop("checked",true);
                            }
                            else {
                                $(this).prop("checked",false);
                            }
                        });

                    });
                }
            }
        },
        error: function (error) {
        }
    })
});

$('#multiple_column_form').submit(function(event) {
    event.preventDefault();
    $.post($(this).attr("action"), $(this).serialize(),
        function(response) {
            if (response.success) {
                location.reload(true);
            }
            else {
                alert("Convert error : " + response.message);
            }
        }
    );
});

/* END OF JSON EDITOR'S */

var stats_tpl = $('#stats-template');
var errors_tpl = $('#errors-template');
var exceptions_tpl = $('#exceptions-template');

$('#swarm_form').submit(function(event) {
    event.preventDefault();
    $.post($(this).attr("action"), $(this).serialize(),
        function(response) {
            if (response.success) {
                $("body").attr("class", "hatching");
                $("#start").fadeOut();
                $("#status").fadeIn();
                $(".box_running").fadeIn();
                $("a.new_test").fadeOut();
                $("a.edit_test").fadeIn();
                $(".user_count").fadeIn();
                resetCharts();
            }
        }
    );
});

$('#edit_form').submit(function(event) {
    event.preventDefault();
    $.post($(this).attr("action"), $(this).serialize(),
        function(response) {
            if (response.success) {
                $("body").attr("class", "hatching");
                $("#edit").fadeOut();
            }
        }
    );
});

var sortBy = function(field, reverse, primer){
    reverse = (reverse) ? -1 : 1;
    return function(a,b){
        a = a[field];
        b = b[field];
       if (typeof(primer) != 'undefined'){
           a = primer(a);
           b = primer(b);
       }
       if (a<b) return reverse * -1;
       if (a>b) return reverse * 1;
       return 0;
    }
}

// Sorting by column
var sortAttribute = "name";
var desc = false;
var report;
$(".stats_label").click(function(event) {
    event.preventDefault();
    sortAttribute = $(this).attr("data-sortkey");
    desc = !desc;

    $('#stats tbody').empty();
    $('#errors tbody').empty();
    alternate = false;
    totalRow = report.stats.pop()
    sortedStats = (report.stats).sort(sortBy(sortAttribute, desc))
    sortedStats.push(totalRow)
    $('#stats tbody').jqoteapp(stats_tpl, sortedStats);
    alternate = false;
    $('#errors tbody').jqoteapp(errors_tpl, (report.errors).sort(sortBy(sortAttribute, desc)));
});

// init charts
var rpsChart, responseTimeChart, usersChart, failureChart, endpointResponseTimeCharts, endpointRpsCharts, endpointFailureCharts, advanceChart;
const totalKey = "total"

function updateStats() {
    $.get('/stats/requests', function (data) {
        report = JSON.parse(data);
        $("#total_rps").html(Math.round(report.total_rps*100)/100);
        $("#fail_ratio").html(Math.round(report.fail_ratio*100));
        $("#status_text").html(report.state);
        $("#userCount").html(report.user_count);
        $("#running_type").html(report.running_type);
        $("#host_url").html(report.host)

        if (typeof report.slave_count !== "undefined")
            $("#slaveCount").html(report.slave_count)

        RAMP = "Auto"
        if (report.running_type == RAMP) {
            $(".edit_test").addClass("none")
        } else {
            $(".edit_test").removeClass("none")
        }

        $('#stats tbody').empty();
        $('#errors tbody').empty();

        //Handle if user request to reset stats
        if(report.total_run_time < runTime ) {
          runTime = report.total_run_time;
          $("#run_time").html(String(runTime).toHHMMSS())
        }

        alternate = false;

        totalRow = report.stats.pop()
        sortedStats = (report.stats).sort(sortBy(sortAttribute, desc))
        sortedStats.push(totalRow)
        $('#stats tbody').jqoteapp(stats_tpl, sortedStats);
        alternate = false;
        $('#errors tbody').jqoteapp(errors_tpl, (report.errors).sort(sortBy(sortAttribute, desc)));

        if (report.state !== "stopped"){
            // get total stats row
            var total = report.stats[report.stats.length-1];

            endpointChartSize = report.stats.length - 1
            rpsValues = []
            responseTimeValues = []
            failureValues = []
            let statsNoTotal = report.stats.splice(0,endpointChartSize)
            if(statsNoTotal.length > 1) {
              statsNoTotal = statsNoTotal.sort(function(a, b) {
                let keyA = a.name.toUpperCase() + a.method.toUpperCase(); // ignore upper and lowercase
                let keyB = b.name.toUpperCase() + b.method.toUpperCase(); // ignore upper and lowercase
                if (keyA < keyB) return -1;
                if (keyA > keyB) return 1;
                return 0;
              })
            }
            for (let i=0; i < statsNoTotal.length; i++) {
              chartKey = statsNoTotal[i].name.toUpperCase() + statsNoTotal[i].method.toUpperCase()
              createEndpointLines(chartKey, statsNoTotal[i].name, (chartKey) => {
                rpsValues.push(statsNoTotal[i].current_rps)
                responseTimeValues.push(statsNoTotal[i].avg_response_time)
                failureValues.push(statsNoTotal[i].num_failures)
              })
            }
            endpointResponseTimeCharts[totalKey].addValue([total.avg_response_time]);
            endpointRpsCharts[totalKey].addValue([total.current_rps]);
            endpointFailureCharts[totalKey].addValue([total.num_failures]);
            failureChart.addValue(failureValues);
            rpsChart.addValue(rpsValues);
            responseTimeChart.addValue(responseTimeValues);
            advanceChart.addValue([[report.user_count],rpsValues,responseTimeValues,failureValues])
            usersChart.addValue([report.user_count]);
        }

        setTimeout(updateStats, 2000);
    });
}
updateStats();

function updateExceptions() {
    $.get('/exceptions', function (data) {
        $('#exceptions tbody').empty();
        $('#exceptions tbody').jqoteapp(exceptions_tpl, data.exceptions);
        setTimeout(updateExceptions, 5000);
    });
}
updateExceptions();

function createEndpointLines(chartKey, name, callback) {
    if(!rpsChart.isLineExist(chartKey)) rpsChart.addLine(chartKey, name);
    if(!responseTimeChart.isLineExist(chartKey)) responseTimeChart.addLine(chartKey , name);
    if(!failureChart.isLineExist(chartKey)) failureChart.addLine(chartKey, name);
    if(!advanceChart.isLineExist(1,chartKey)) {
        for(let l=1; l < chartFilters.length; l++) {
            advanceChart.addLine(l,chartKey,name)
        }
    }
    callback(chartKey)
}

function resetCharts() {
  if (!!rpsChart) rpsChart.dispose()
  if (!!responseTimeChart) responseTimeChart.dispose()
  if (!!usersChart) usersChart.dispose()
  if (!!failureChart) failureChart.dispose()
  if (!!advanceChart) advanceChart.dispose()
  if (!!endpointResponseTimeCharts) {
    for (var chartKey in endpointResponseTimeCharts) {
      endpointResponseTimeCharts[chartKey].dispose()
      endpointRpsCharts[chartKey].dispose()
      endpointFailureCharts[chartKey].dispose()
    }
  }
  $('.charts-container').empty()
  advanceChart = new LocustAdvanceLineChart($(".charts-container"), "Advance Chart", "", chartFilters, ['users','reqs/s','ms','failures'], "100%");
  rpsChart = new LocustLineChart($(".charts-container"), "Requests per Second", "", [], "reqs/s", "100%");
  responseTimeChart = new LocustLineChart($(".charts-container"), "Average Response Time", "", [], "ms", "100%");
  usersChart = new LocustLineChart($(".charts-container"), "Number of Users", "", ["Total"], "users", "100%");
  failureChart = new LocustLineChart($(".charts-container"), "Number of Failures", "", [], "failures", "100%");
  advanceChart.addLine(0,"Total","Total")
  $(".chart-filter > button")[chartFilters.indexOf('response time')].click()
  endpointResponseTimeCharts = []
  endpointRpsCharts = []
  endpointFailureCharts = []
  initTotalCharts()
}
resetCharts()

function initTotalCharts() {
  endpointResponseTimeCharts[totalKey] = new LocustLineChart($(".charts-container"), "Average Responses Time", totalKey.toUpperCase(), ["Average Responses Time"], "ms", "33.3%");
  endpointRpsCharts[totalKey] = new LocustLineChart($(".charts-container"), "Requests Per Second", totalKey.toUpperCase(), ["RPS"], "request", "33.3%");
  endpointFailureCharts[totalKey] = new LocustLineChart($(".charts-container"), "Failure", totalKey.toUpperCase(), ["Failures"], "failure", "33.3%");
}