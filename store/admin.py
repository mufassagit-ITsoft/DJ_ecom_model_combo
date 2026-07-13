from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe   
from django.urls import reverse
from . models import Category, Product, Topic

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    
    # Display these fields in the product list view
    list_display = [
        'title',
        'brand',
        'upc_badge',
        'price',
        'quantity_available',
        'quantity_sold',
        'total_price_sold',
        'date_uploaded',
        'last_sold_date',
        'payment_successful',
        'stock_status'
    ]
    
    # Add filters for easy navigation
    list_filter = [
        'payment_successful',
        'category',
        'brand',
        'date_uploaded',
        'last_sold_date'
    ]
    
    # Add search functionality
    search_fields = ['title', 'brand', 'description', 'upc_code']
    
    # Make these fields read-only (auto-calculated)
    readonly_fields = [
        'date_uploaded',
        'quantity_sold',
        'total_price_sold',
        'last_sold_date',
        'payment_successful',
        'barcode_scanner_widget',
    ]
    
    # Organize fields in the edit form
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'brand', 'category', 'description', 'price', 'image')
        }),
        ('Barcode / UPC', {
            'fields': ('barcode_scanner_widget', 'upc_code'),
            'description': (
                'Scan a product barcode with your camera, plug in a USB/Bluetooth hand scanner '
                'and scan directly into the input field, or type the UPC manually. '
                'Product details will be pre-filled from the UPCitemdb registry.'
            )
        }),
        ('Inventory Management', {
            'fields': ('quantity_available',),
            'description': 'Set the available stock quantity for this product'
        }),
        ('Sales Tracking (Read-Only)', {
            'fields': (
                'date_uploaded', 'quantity_sold',
                'total_price_sold', 'last_sold_date', 'payment_successful'
            ),
            'description': 'These fields are automatically updated when sales occur',
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-date_uploaded']

    # Custom method to display stock status
    def stock_status(self, obj):
        if obj.quantity_available > 10:
            return f"✅ In Stock ({obj.quantity_available})"
        elif obj.quantity_available > 0:
            return f"⚠️ Low Stock ({obj.quantity_available})"
        else:
            return "❌ Out of Stock"
    
    stock_status.short_description = 'Stock Status'
    
    # Order by most recently added by default
    ordering = ['-date_uploaded']

    def upc_badge(self, obj):
        if obj.upc_code:
            return format_html(
                '<span style="background:#28a745;color:white;padding:2px 8px;'
                'border-radius:10px;font-size:11px;">&#128230; {}</span>',
                obj.upc_code
            )
        return mark_safe(
            '<span style="background:#6c757d;color:white;padding:2px 8px;'
            'border-radius:10px;font-size:11px;">No UPC</span>'
        )
    upc_badge.short_description = 'UPC Code'

    def barcode_scanner_widget(self, obj):
        """
        Inline barcode scanner in the product admin form.

        Supports three input methods:
          1. USB/Bluetooth hand scanner — click the input box, scan,
             the UPC auto-types and triggers lookup automatically.
          2. Camera scanner (QuaggaJS) — click Start Camera, point at barcode.
          3. Manual keyboard entry — type UPC, press Enter or click Look Up.

        On successful lookup, auto-fills title/brand/description/price/upc_code.

        FIX: Returns mark_safe() instead of format_html() because the HTML
        is pre-built as a plain string. format_html() raises:
          TypeError: args or kwargs must be provided
        when called with a string but no escaping arguments (Django 4.0+ safety check).
        mark_safe() is correct here since we control the entire string.
        """
        lookup_url = reverse('barcode-lookup')

        widget_html = (
            '<div id="barcode-admin-widget" style="'
            'border:2px solid #dee2e6;border-radius:8px;'
            'padding:20px;background:#f8f9fa;max-width:600px;">'

            '<h4 style="margin-top:0;color:#333;">&#128247; Barcode Scanner</h4>'
            '<p style="color:#666;font-size:13px;margin-bottom:15px;">'
            '<strong>Hand scanner:</strong> Click the input box below, then scan &mdash; '
            'the UPC will auto-type and trigger the lookup automatically.<br>'
            '<strong>Camera:</strong> Click Start Camera and point at the barcode.<br>'
            '<strong>Manual:</strong> Type the UPC and press Enter or click Look Up.'
            '</p>'

            '<button type="button" id="toggle-camera-btn" onclick="toggleBarcodeCamera()" '
            'style="background:#007bff;color:white;border:none;padding:8px 16px;'
            'border-radius:5px;cursor:pointer;margin-bottom:10px;">'
            '&#128247; Start Camera Scanner'
            '</button>'

            '<div id="barcode-camera-container" style="display:none;margin-bottom:15px;">'
            '<div id="barcode-viewport" style="width:100%;max-width:400px;height:250px;'
            'border:3px solid #007bff;border-radius:8px;overflow:hidden;'
            'position:relative;background:#000;">'
            '<p style="color:white;text-align:center;padding-top:110px;font-size:12px;">'
            'Camera loading...</p></div>'
            '<p style="font-size:12px;color:#666;margin-top:5px;">'
            'Point camera at barcode &mdash; detection is automatic.</p>'
            '</div>'

            '<div style="display:flex;gap:10px;align-items:center;margin-bottom:15px;">'
            '<input type="text" id="manual-upc-input" '
            'placeholder="Hand scanner: click here then scan | or type UPC e.g. 045496596248" '
            'style="flex:1;padding:8px 12px;border:2px solid #ced4da;'
            'border-radius:5px;font-size:14px;" />'
            '<button type="button" id="upc-lookup-btn" '
            'style="background:#28a745;color:white;border:none;padding:8px 16px;'
            'border-radius:5px;cursor:pointer;white-space:nowrap;">'
            '&#128269; Look Up'
            '</button>'
            '</div>'

            '<div id="barcode-status" style="display:none;padding:10px;'
            'border-radius:5px;font-size:13px;"></div>'

            '<div id="barcode-preview" style="display:none;margin-top:15px;'
            'background:white;border:1px solid #dee2e6;border-radius:5px;padding:15px;">'
            '<strong style="color:#28a745;">&#10003; Product found &mdash; '
            'details pre-filled below</strong>'
            '<div id="barcode-preview-content" '
            'style="margin-top:10px;font-size:13px;color:#555;"></div>'
            '<p style="font-size:12px;color:#888;margin-top:10px;margin-bottom:0;">'
            'Review the pre-filled fields and adjust before saving.</p>'
            '</div>'
            '</div>'

            '<script src="https://cdnjs.cloudflare.com/ajax/libs/quagga/0.12.1/quagga.min.js">'
            '</script>'
            '<script>'
            '(function(){'
            'var LOOKUP_URL="' + lookup_url + '";'
            'var cameraActive=false;'

            'var inp=document.getElementById("manual-upc-input");'
            'inp.addEventListener("keypress",function(e){'
            'if(e.key==="Enter"){e.preventDefault();lookupUPC(this.value);}});'
            'document.getElementById("upc-lookup-btn").addEventListener("click",function(){'
            'lookupUPC(document.getElementById("manual-upc-input").value);});'

            'window.toggleBarcodeCamera=function(){'
            'var btn=document.getElementById("toggle-camera-btn");'
            'var con=document.getElementById("barcode-camera-container");'
            'if(!cameraActive){'
            'con.style.display="block";'
            'btn.textContent="\u23F9 Stop Camera";btn.style.background="#dc3545";'
            'startBarcodeScanner();cameraActive=true;'
            '}else{'
            'con.style.display="none";'
            'btn.textContent="Start Camera Scanner";btn.style.background="#007bff";'
            'if(typeof Quagga!=="undefined")Quagga.stop();cameraActive=false;}};'

            'function startBarcodeScanner(){'
            'Quagga.init({'
            'inputStream:{name:"Live",type:"LiveStream",'
            'target:document.getElementById("barcode-viewport"),'
            'constraints:{facingMode:"environment",width:{min:400},height:{min:250}}},'
            'decoder:{readers:["upc_reader","upc_e_reader","ean_reader",'
            '"ean_8_reader","code_128_reader"]},'
            'locate:true'
            '},function(err){'
            'if(err){showStatus("Camera error: "+err.message+". Use manual entry.","error");'
            'window.toggleBarcodeCamera();return;}'
            'Quagga.start();});'
            'var lc="",lt=0;'
            'Quagga.onDetected(function(r){'
            'var c=r.codeResult.code,n=Date.now();'
            'if(c===lc&&n-lt<3000)return;lc=c;lt=n;'
            'if(typeof Quagga!=="undefined")Quagga.stop();'
            'window.toggleBarcodeCamera();'
            'document.getElementById("manual-upc-input").value=c;'
            'lookupUPC(c);});}'

            'function lookupUPC(upc){'
            'upc=upc.trim();'
            'if(!upc){showStatus("Please enter or scan a UPC code.","error");return;}'
            'showStatus("Looking up UPC "+upc+"...","info");'
            'fetch(LOOKUP_URL+"?upc="+encodeURIComponent(upc))'
            '.then(function(r){return r.json();})'
            '.then(function(data){'
            'if(data.error){showStatus("\u274C "+data.error,"error");return;}'
            'var p=data.product;'
            'if(data.found_locally){'
            'showStatus("\u2705 Already in your store: <strong>"+p.title+"</strong>.'
            ' <a href=\\"/admin/store/product/"+p.id+"/change/\\" '
            'style=\\"color:#007bff;\\">View/Edit \u2192</a>","warning");'
            'return;}'
            'if(!p){'
            'showStatus("\u26A0\uFE0F UPC "+upc+" not in registry. Enter details manually.","warning");'
            'fillField("id_upc_code",upc);return;}'
            'fillField("id_upc_code",p.upc_code||upc);'
            'fillField("id_title",p.title||"");'
            'fillField("id_brand",p.brand||"");'
            'fillField("id_description",p.description||"");'
            'if(p.price)fillField("id_price",p.price);'
            'var prev="<strong>"+(p.title||"Unknown")+"</strong>"'
            '+(p.brand?" \u2014 "+p.brand:"")'
            '+(p.price?" | $"+p.price:"")'
            '+(p.description'
            '?"<br><span style=\'color:#777\'>"+p.description.substring(0,120)+"...</span>":"");'
            'document.getElementById("barcode-preview-content").innerHTML=prev;'
            'document.getElementById("barcode-preview").style.display="block";'
            'showStatus("\u2705 Details fetched. Review and save.","success");'
            '}).catch(function(err){'
            'showStatus("\u274C Lookup failed: "+err.message,"error");});}'

            'function fillField(id,val){'
            'var el=document.getElementById(id);'
            'if(el&&val){el.value=val;'
            'if(id==="id_title"){'
            'el.dispatchEvent(new Event("input",{bubbles:true}));'
            'el.dispatchEvent(new Event("keyup",{bubbles:true}));}}}'

            'function showStatus(msg,type){'
            'var el=document.getElementById("barcode-status");'
            'var cols={'
            'success:{bg:"#d4edda",color:"#155724",border:"#c3e6cb"},'
            'error:{bg:"#f8d7da",color:"#721c24",border:"#f5c6cb"},'
            'warning:{bg:"#fff3cd",color:"#856404",border:"#ffeeba"},'
            'info:{bg:"#d1ecf1",color:"#0c5460",border:"#bee5eb"}'
            '};'
            'var c=cols[type]||cols.info;'
            'el.style.display="block";el.style.background=c.bg;'
            'el.style.color=c.color;el.style.border="1px solid "+c.border;'
            'el.innerHTML=msg;}'

            '})();'
            '</script>'
        )
        return mark_safe(widget_html)

    barcode_scanner_widget.short_description = 'Barcode Scanner'


