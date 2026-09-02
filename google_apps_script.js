// Set your Python tracking server URL here (e.g., your Raspberry Pi public IP or ngrok domain)
const TRACKING_SERVER_URL = "https://your-custom-domain.com";

function processTrackedDrafts() {
    var label;
    try {
        label = GmailApp.getUserLabelByName("TrackMe");
    } catch (e) {
        console.error("Error fetching label 'TrackMe': " + e);
        return;
    }

    // If the label doesn't exist, log an error and exit
    if (!label) {
        console.error("The label 'TrackMe' was not found. Please create it first.");
        return;
    }

    // Optimization: First check if there are any threads with the label AND a draft.
    // If none exist, we can exit early and save API calls.
    var trackedThreads;
    try {
        trackedThreads = GmailApp.search('label:TrackMe is:draft');
    } catch (e) {
        console.error("Error searching for tracked threads: " + e);
        return;
    }

    if (trackedThreads.length === 0) {
        return; // Exits naturally cleanly
    }

    // Identify exactly which message IDs are the drafts we need to modify
    var targetMessageIds = [];
    for (var i = 0; i < trackedThreads.length; i++) {
        try {
            var messages = trackedThreads[i].getMessages();
            for (var j = 0; j < messages.length; j++) {
                try {
                    if (messages[j].isDraft()) {
                        targetMessageIds.push(messages[j].getId());
                    }
                } catch (innerE) {
                    console.error("Error processing message " + j + " in thread " + i + ": " + innerE);
                }
            }
        } catch (e) {
            console.error("Error retrieving messages for thread " + i + ": " + e);
        }
    }

    if (targetMessageIds.length === 0) {
        return; // Safety exit
    }

    var drafts;
    try {
        drafts = GmailApp.getDrafts();
    } catch (e) {
        console.error("Error fetching drafts: " + e);
        return;
    }

    var draftsProcessed = 0;
    var totalToProcess = targetMessageIds.length;

    for (var i = 0; i < drafts.length; i++) {
        if (draftsProcessed >= totalToProcess) {
            break; // Stop immediately once all target drafts are processed to avoid execution timeout
        }

        try {
            var draft = drafts[i];
            var message = draft.getMessage();

            // Check if this draft is one of our target drafts natively
            if (targetMessageIds.indexOf(message.getId()) !== -1) {
                draftsProcessed++; // Increment early to ensure we don't scan all drafts if an error occurs below

                var body = message.getBody();
                
                var rawTo = message.getTo() || "";
                var recipients = rawTo.split(',').map(function(e) { return e.trim(); }).filter(function(e) { return e.length > 0; });
                
                if (recipients.length === 0) {
                    console.error("No recipients found for draft " + message.getId());
                    continue;
                }

                var rawFrom = message.getFrom() || "";
                var accountMatch = rawFrom.match(/<([^>]+)>/);
                var account = accountMatch ? accountMatch[1] : rawFrom.trim();
                if (!account) account = "Unknown Account";
                
                var aliases = GmailApp.getAliases();

                for (var r = 0; r < recipients.length; r++) {
                    var recipient = recipients[r];
                    // Generate a unique ID for this email, add random to prevent duplicates if processed in the same millisecond
                    var emailId = "id_" + new Date().getTime() + "_" + Math.floor(Math.random() * 10000);

                    var encSubj = encodeURIComponent(message.getSubject() || "No Subject");
                    var encTo = encodeURIComponent(recipient);
                    var encAccount = encodeURIComponent(account);

                    // 1. Inject Open Tracker (Python Server)
                    var pixelUrl = TRACKING_SERVER_URL + '/open/' + emailId + '?subject=' + encSubj + '&recipient=' + encTo + '&account=' + encAccount;
                    var pixel = '<img src="' + pixelUrl + '" width="1" height="1" alt="" style="display:none;" />';

                    // 2. Wrap Links for Click Tracking
                    var trackedBody = body.replace(/href="([^"]*)"/gi, function (match, p1) {
                        // Don't double-wrap or wrap internal protocol links (mailto:)
                        if (p1.includes(TRACKING_SERVER_URL) || p1.startsWith("mailto:")) {
                            return match;
                        }
                        return 'href="' + TRACKING_SERVER_URL + '/click?id=' + emailId + '&subject=' + encSubj + '&recipient=' + encTo + '&account=' + encAccount + '&url=' + encodeURIComponent(p1) + '"';
                    });

                    // 3. Send or Update Draft
                    // If multiple recipients, strip CC/BCC to avoid spamming them for every individual email
                    var isMultiple = recipients.length > 1;
                    var cc = isMultiple ? "" : message.getCc();
                    var bcc = isMultiple ? "" : message.getBcc();
                    var attachments = message.getAttachments();

                    if (r === recipients.length - 1) {
                        // Last recipient: update the original draft and send it. This cleans up the draft.
                        var updatedDraft = draft.update(recipient, message.getSubject(), "", {
                            htmlBody: trackedBody + pixel,
                            cc: cc,
                            bcc: bcc,
                            attachments: attachments
                        });
                        Utilities.sleep(1000);
                        updatedDraft.send();
                    } else {
                        // Other recipients: send as new emails
                        var sendOptions = {
                            htmlBody: trackedBody + pixel,
                            cc: cc,
                            bcc: bcc,
                            attachments: attachments
                        };
                        // Only pass 'from' if it's a verified alias, otherwise it defaults to the primary account
                        if (aliases.indexOf(account) !== -1) {
                            sendOptions.from = account;
                        }
                        GmailApp.sendEmail(recipient, message.getSubject(), "", sendOptions);
                        Utilities.sleep(1000); // Prevent rate limiting
                    }

                    console.log("Sent tracked email with ID: " + emailId + " to: " + recipient);
                }
            }
        } catch (e) {
            console.error("Error processing individual draft at index " + i + ": " + e);
            // Skip this faulty draft but keep processing others until we break
            continue;
        }
    }
}
