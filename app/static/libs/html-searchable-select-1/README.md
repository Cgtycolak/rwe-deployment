# html-searchable-select
html-searchable-select is a JS plugin that converts your HTML multiple select element into a searchable HTML multiple select. Your original select element remains unchanged, allowing you to use any JavaScript code to access the values of the searchable multiple select, no javascript exp required to control or customize the new html multiple select with search generated just data attributes to full customize it

# how to start:
* check examples.html
* Include the html_multiple_select.js file in your code, then create as many select elements in HTML as you need, in any way you prefer. Finally, create a new instance of HTMLSearchableSelect and provide any DOM selector for the class.

### Examples:
![image](https://github.com/user-attachments/assets/5899bf22-7805-4297-a043-912acf2a4e20)
A few examples of dynamic, customized select elements that are all controlled by HTML data attributes in the provided HTML code. As noted, this plugin is the best option for use with any backend or backend libraries, such as WTForms for Python, direct integration into WordPress PHP, or controlling attributes with Jinja2 or Thymeleaf in Java Spring Boot, for example. Additionally, there is no need to use any JavaScript methods to access the values.

###### If you ask, I want to clarify that a lot of JavaScript is needed. Note that all JavaScript examples use the same two words; that's why the plugin name starts with HTML word, 'HTMLSearchableSelect,' is not just a name but also a definition and documentation guideline.

```javascript
new HTMLSearchableSelect("#select_orgs");
new HTMLSearchableSelect("#select_orgs2");
new HTMLSearchableSelect("#select_orgs3");
```
